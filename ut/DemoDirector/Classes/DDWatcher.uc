//=============================================================================
// DDWatcher - client-side actor living in the demo level.
//  * periodic playback state (STATE)
//  * score / death deltas per player, death context (DEATH)
//  * rich scan mode (bRich): player positions (POS), shock balls (BALLEND),
//    combo explosions (COMBO), shots (SHOT), flag bases (FLAGBASE), player ids (PID)
//  * gore filter (bNoGore): hides gibs, carcasses and blood effects
//  * clean HUD swap (Con.bCleanHud) and class census (bCensus)
// Player names can contain any character, so rich lines use PlayerIDs; PID lines map
// id -> name (name is always the LAST field of a PID line).
//=============================================================================
class DDWatcher extends Info;

var DDConsole Con;
var float Accum;
var float ReportInterval;

// per player slots (indexed like KPRI)
var PlayerReplicationInfo KPRI[64];
var float KScore[64];
var float KDeaths[64];
var vector KLoc[64];
var vector KVel[64];
var int KPhys[64];         // height above ground (uu), measured with a trace
var int KFlag[64];        // team of the flag carried, -1 none
var int KTeam[64];        // last logged team (for PID lines), -2 = never logged
var string KName[64];     // last logged name
var int KCount;

var HUD OrigHUD;
var DDBlankHUD BlankHUD;
var DDCineHUD CineHUD;
var DDCam Cam;
var DDTake Take;
var DDBullet Bullet;

// kill probe ("ddprobe k=<id> v=<id>"): logs both pawns every tick and new carcasses, to find the exact demo time
// and positions of a kill
var bool bProbe;
var int ProbeK, ProbeV;
var Actor ProbeSeen[32];
var int ProbePos;
var vector ProbeVLoc;

// class census (discovery of mod classes): logs each new actor class once
var bool bCensus;
var float CensusAccum;
var string SeenClass[512];
var int SeenCount;

// rich scan mode
var bool bRich;
var bool bBasesLogged;
var float PosAccum;
var float PosInterval;
var Projectile BallA[64];
var float BallT0[64];
var vector BallLoc0[64];
var vector BallLast[64];
var vector BallShooter0[64];
var int BallBy[64];
var int BallN;
var int BallSeq;
var Actor RingSeen[32];
var int RingPos;
var Actor BeamSeen[64];
var int BeamPos;

// beam log ("ddbeams 1"): every shock beam actor once, with everything needed to tell duplicates apart
var bool bBeamLog;
var Actor BeamLogSeen[128];
var string BeamLogSig[128];
var int BeamLogPos;

// ZeroPing beam fix (on by default, "ddbeamfix 0" turns it off), see BeamFix()
var bool bBeamFix;

// gore filter
var bool bNoGore;

// speed ramp: keyframes in demo time, exponential speed interpolation between them ("ddramp t:s,t:s,...")
var float RampT[8];
var float RampS[8];
var int RampN;
var float RampLastSet;

function DemoPlaybackSpec Spec()
{
	if (Con != None && Con.Viewport != None)
		return DemoPlaybackSpec(Con.Viewport.Actor);
	return None;
}

function string ActorName(Actor A)
{
	if (A == None)
		return "";
	if (Pawn(A) != None && Pawn(A).PlayerReplicationInfo != None)
		return Pawn(A).PlayerReplicationInfo.PlayerName;
	return string(A.Class.Name);
}

function string V(vector X)
{
	return int(X.X) $ "," $ int(X.Y) $ "," $ int(X.Z);
}

function float DemoTime()
{
	local DemoPlaybackSpec S;
	S = Spec();
	if (S != None && S.Driver != None)
		return S.Driver.GetCurrentTime();
	return -1;
}

// --- speed ramp ---------------------------------------------------------------------
function SetRamp(string S)
{
	local int i;
	local string Pair, Orig;
	Orig = S;
	RampN = 0;
	RampLastSet = 0;
	S = S $ ",";
	while (RampN < 8)
	{
		i = InStr(S, ",");
		if (i < 0) break;
		Pair = Left(S, i);
		S = Mid(S, i + 1);
		if (InStr(Pair, ":") >= 0)
		{
			RampT[RampN] = float(Left(Pair, InStr(Pair, ":")));
			RampS[RampN] = FMax(float(Mid(Pair, InStr(Pair, ":") + 1)), 0.001);
			if (RampN == 0 || RampT[RampN] > RampT[RampN - 1])   // keyframes must ascend
				RampN++;
		}
	}
	Con.DDLog("RAMP", "n=" $ RampN $ "|args=" $ Orig);
	ApplyRamp(true);
}

function float SpeedAt(float T)
{
	local int i;
	local float U;
	if (RampN == 0) return 1;
	if (T <= RampT[0]) return RampS[0];
	for (i = 0; i < RampN - 1; i++)
		if (T < RampT[i + 1])
		{
			U = (T - RampT[i]) / (RampT[i + 1] - RampT[i]);
			return RampS[i] * Exp(U * Loge(RampS[i + 1] / RampS[i]));
		}
	return RampS[RampN - 1];
}

// wall seconds of playback for demo interval [A, B] under the ramp (integral of 1/speed)
function float SegWall(float A, float B, float T0, float T1, float S0, float S1)
{
	local float L, LR, UA, UB;
	if (B <= A) return 0;
	L = T1 - T0;
	LR = Loge(S1 / S0);
	if (Abs(LR) < 0.0001) return (B - A) / S0;
	UA = (A - T0) / L; UB = (B - T0) / L;
	return L / (S0 * LR) * (Exp(-UA * LR) - Exp(-UB * LR));
}

function float WallBetween(float A, float B)
{
	local int i;
	local float W;
	if (B <= A) return 0;
	if (RampN == 0) return B - A;
	if (A < RampT[0]) W += (FMin(B, RampT[0]) - A) / RampS[0];
	for (i = 0; i < RampN - 1; i++)
		W += SegWall(FMax(A, RampT[i]), FMin(B, RampT[i + 1]), RampT[i], RampT[i + 1], RampS[i], RampS[i + 1]);
	if (B > RampT[RampN - 1]) W += (B - FMax(A, RampT[RampN - 1])) / RampS[RampN - 1];
	return W;
}

function ApplyRamp(bool bForce)
{
	local DemoPlaybackSpec S;
	local float Want;
	S = Spec();
	if (RampN == 0 || S == None || S.Driver == None || S.bSeeking)
		return;
	Want = SpeedAt(DemoTime());
	if (bForce || RampLastSet <= 0 || Abs(Want / RampLastSet - 1) > 0.003)
	{
		S.Driver.SetSpeed(Want);
		RampLastSet = Want;
	}
}

function ReportState(string Tag)
{
	local DemoPlaybackSpec S;
	local DemoInterface D;
	local string Txt;
	S = Spec();
	if (S == None || S.Driver == None)
		return;
	D = S.Driver;
	Txt = "total=" $ D.GetTotalTime()
		$ "|frame=" $ D.GetCurrentFrame()
		$ "|speed=" $ D.mySpeed
		$ "|paused=" $ D.IsPaused()
		$ "|seeking=" $ S.bSeeking
		$ "|view=" $ ActorName(S.ViewTarget)
		$ "|behind=" $ S.bBehindView
		$ "|linked=" $ ActorName(S.PlayerLinked)
		$ "|lts=" $ Level.TimeSeconds;
	if (Level.Game == None && S.GameReplicationInfo != None)
		Txt = Txt $ "|remain=" $ S.GameReplicationInfo.RemainingTime;
	Con.DDLog(Tag, Txt);
}

function ReportPlayers()
{
	local PlayerReplicationInfo P;
	foreach AllActors(class'PlayerReplicationInfo', P)
		Con.DDLog("PLAYER", "name=" $ P.PlayerName $ "|id=" $ P.PlayerID $ "|team=" $ P.Team
			$ "|score=" $ int(P.Score) $ "|deaths=" $ int(P.Deaths) $ "|spec=" $ P.bIsSpectator
			$ "|bot=" $ P.bIsABot);
	Con.DDLog("PLAYERS_END", "");
}

// Returns the slot of P (creating it if needed); bNew is true for a new slot.
function int Slot(PlayerReplicationInfo P, out int bNew)
{
	local int i;
	bNew = 0;
	for (i = 0; i < KCount; i++)
		if (KPRI[i] == P)
			return i;
	if (KCount >= 64)
		return -1;
	KPRI[KCount] = P;
	KScore[KCount] = P.Score;
	KDeaths[KCount] = P.Deaths;
	KFlag[KCount] = -1;
	KPhys[KCount] = 0;
	KTeam[KCount] = -2;
	KName[KCount] = "";
	bNew = 1;
	KCount++;
	return KCount - 1;
}

function ScanScores()
{
	local PlayerReplicationInfo P;
	local int i, bNew;
	local DemoPlaybackSpec S;
	S = Spec();
	if (S != None && S.bSeeking)
		return;
	foreach AllActors(class'PlayerReplicationInfo', P)
	{
		i = Slot(P, bNew);
		if (i < 0 || bNew == 1)
			continue;
		if (P.Score != KScore[i])
		{
			Con.DDLog("SCORE", "name=" $ P.PlayerName $ "|from=" $ int(KScore[i]) $ "|to=" $ int(P.Score));
			KScore[i] = P.Score;
		}
		if (P.Deaths != KDeaths[i])
		{
			// last known state of the victim (cached from previous ticks)
			Con.DDLog("DEATH", "id=" $ P.PlayerID $ "|loc=" $ V(KLoc[i]) $ "|vel=" $ V(KVel[i]) $ "|h=" $ KPhys[i]
				$ "|flag=" $ KFlag[i] $ "|from=" $ int(KDeaths[i]) $ "|to=" $ int(P.Deaths) $ "|name=" $ P.PlayerName);
			KDeaths[i] = P.Deaths;
		}
	}
}

// Cache position / velocity / physics / carried flag of every player pawn.
function UpdatePawnCache()
{
	local Pawn P;
	local int i, bNew;
	foreach AllActors(class'Pawn', P)
	{
		if (P.PlayerReplicationInfo == None || P.IsA('Spectator') || P.IsA('DemoPlaybackSpec') || P.Health <= 0)
			continue;
		i = Slot(P.PlayerReplicationInfo, bNew);
		if (i < 0)
			continue;
		KLoc[i] = P.Location;
		KVel[i] = P.Velocity;
		KPhys[i] = Height(P);
		if (CTFFlag(P.PlayerReplicationInfo.HasFlag) != None)
			KFlag[i] = CTFFlag(P.PlayerReplicationInfo.HasFlag).Team;
		else
			KFlag[i] = -1;
	}
}

// Height of the pawn's feet above the floor below it (pawn physics is not replicated in demos).
function int Height(Pawn P)
{
	local vector HL, HN;
	if (Trace(HL, HN, P.Location - vect(0,0,4000), P.Location, false) == None)
		return 4000;
	return int(P.Location.Z - HL.Z - P.CollisionHeight);
}

function vector PawnLocById(int Id)
{
	local int i;
	for (i = 0; i < KCount; i++)
		if (KPRI[i] != None && KPRI[i].PlayerID == Id)
			return KLoc[i];
	return vect(0,0,0);
}

// (Re)log id -> team/name for players whose team or name changed (or were never logged).
function LogPids()
{
	local int i;
	for (i = 0; i < KCount; i++)
	{
		if (KPRI[i] == None)
			continue;
		if (KTeam[i] != KPRI[i].Team || KName[i] != KPRI[i].PlayerName)
		{
			KTeam[i] = KPRI[i].Team;
			KName[i] = KPRI[i].PlayerName;
			Con.DDLog("PID", "id=" $ KPRI[i].PlayerID $ "|team=" $ KPRI[i].Team $ "|spec=" $ KPRI[i].bIsSpectator $ "|name=" $ KPRI[i].PlayerName);
		}
	}
}

function LogPositions()
{
	local Pawn P;
	local CTFFlag F;
	local string S, FS;
	foreach AllActors(class'Pawn', P)
	{
		if (P.PlayerReplicationInfo == None || P.IsA('Spectator') || P.IsA('DemoPlaybackSpec') || P.Health <= 0)
			continue;
		S = S $ P.PlayerReplicationInfo.PlayerID $ ":" $ V(P.Location) $ ":" $ Height(P) $ ":" $ V(P.Velocity) $ ";";
	}
	foreach AllActors(class'CTFFlag', F)
	{
		FS = FS $ F.Team $ ":" $ V(F.Location) $ ":";
		if (F.Holder != None && F.Holder.PlayerReplicationInfo != None)
			FS = FS $ F.Holder.PlayerReplicationInfo.PlayerID;
		else
			FS = FS $ "-1";
		FS = FS $ ":" $ F.bHome $ ";";
	}
	Con.DDLog("POS", "p=" $ S $ "|f=" $ FS);
}

function LogBases()
{
	local FlagBase B;
	foreach AllActors(class'FlagBase', B)
		Con.DDLog("FLAGBASE", "team=" $ B.Team $ "|loc=" $ V(B.Location));
	bBasesLogged = true;
}

function bool InRing(Actor A)
{
	local int i;
	for (i = 0; i < 32; i++)
		if (RingSeen[i] == A)
			return true;
	return false;
}

function bool InBeams(Actor A)
{
	local int i;
	for (i = 0; i < 64; i++)
		if (BeamSeen[i] == A)
			return true;
	return false;
}

function bool IsGore(Actor A)
{
	if (A.IsA('UTCreatureChunks') || A.IsA('Carcass'))
		return true;
	return InStr(Caps(string(A.Class.Name)), "BLOOD") >= 0;
}

// One pass over all actors: track balls, combos, shots; filter gore.
function ActorPass()
{
	local Actor A;
	local Projectile PR;
	local int i, id;
	local bool bKnown;
	foreach AllActors(class'Actor', A)
	{
		if (bNoGore && IsGore(A))
		{
			if (A.Role == ROLE_Authority)
				A.Destroy();
			else
			{
				A.bHidden = true;
				A.DrawType = DT_None;
			}
			continue;
		}
		if (!bRich)
			continue;
		PR = Projectile(A);
		if (PR != None)
		{
			if (PR.IsA('UTChunk') || PR.Instigator == None || PR.Instigator.PlayerReplicationInfo == None)
				continue;
			bKnown = false;
			for (i = 0; i < BallN; i++)
				if (BallA[i] == PR) { bKnown = true; BallLast[i] = PR.Location; break; }
			if (!bKnown && BallN < 64)
			{
				BallA[BallN] = PR;
				BallT0[BallN] = DemoTime();
				BallLoc0[BallN] = PR.Location;
				BallLast[BallN] = PR.Location;
				BallShooter0[BallN] = PR.Instigator.Location;
				BallBy[BallN] = PR.Instigator.PlayerReplicationInfo.PlayerID;
				BallN++;
			}
			continue;
		}
		if (A.IsA('UT_ComboRing') && !InRing(A))
		{
			RingSeen[RingPos] = A;
			RingPos = (RingPos + 1) % 32;
			Con.DDLog("COMBO", "at=" $ V(A.Location));
			continue;
		}
		if (A.IsA('Effects') && Pawn(A.Owner) != None && Pawn(A.Owner).PlayerReplicationInfo != None
			&& InStr(string(A.Class.Name), "ShockBeam") >= 0 && !InBeams(A))
		{
			BeamSeen[BeamPos] = A;
			BeamPos = (BeamPos + 1) % 64;
			id = Pawn(A.Owner).PlayerReplicationInfo.PlayerID;
			Con.DDLog("SHOT", "by=" $ id $ "|from=" $ V(A.Owner.Location) $ "|at=" $ V(A.Location));
		}
	}
	if (!bRich)
		return;
	// balls that disappeared this tick
	for (i = 0; i < BallN; i++)
	{
		if (BallA[i] == None || BallA[i].bDeleteMe)
		{
			BallSeq++;
			Con.DDLog("BALLEND", "seq=" $ BallSeq $ "|by=" $ BallBy[i] $ "|t0=" $ BallT0[i] $ "|start=" $ V(BallLoc0[i])
				$ "|end=" $ V(BallLast[i]) $ "|s0=" $ V(BallShooter0[i]) $ "|s1=" $ V(PawnLocById(BallBy[i])));
			BallN--;
			BallA[i] = BallA[BallN]; BallT0[i] = BallT0[BallN]; BallLoc0[i] = BallLoc0[BallN];
			BallLast[i] = BallLast[BallN]; BallShooter0[i] = BallShooter0[BallN]; BallBy[i] = BallBy[BallN];
			BallA[BallN] = None;
			i--;
		}
	}
}

// HUD modes: 0 original, 1 cinematic (DDCineHUD), 2 blank (DDBlankHUD), 3 DDCineHUD without messages.
function UpdateHud()
{
	local PlayerPawn P;
	local HUD Want;
	if (Con.Viewport == None)
		return;
	P = Con.Viewport.Actor;
	if (P == None)
		return;
	// remember the original HUD (anything that is not ours)
	if (P.myHUD != None && P.myHUD != BlankHUD && P.myHUD != CineHUD)
		OrigHUD = P.myHUD;
	if (Con.HudMode == 2)
	{
		if (BlankHUD == None)
			BlankHUD = Spawn(class'DDBlankHUD', P);
		Want = BlankHUD;
	}
	else if (Con.HudMode == 1 || Con.HudMode == 3)
	{
		if (CineHUD == None)
		{
			CineHUD = Spawn(class'DDCineHUD', P);
			if (CineHUD != None)
				CineHUD.Con = Con;
		}
		Want = CineHUD;
	}
	else
		Want = OrigHUD;
	if (Want != None && P.myHUD != Want)
		P.myHUD = Want;
}

function Census()
{
	local Actor A;
	local string N;
	local int i;
	local bool bFound;
	foreach AllActors(class'Actor', A)
	{
		N = string(A.Class);
		bFound = false;
		for (i = 0; i < SeenCount; i++)
			if (SeenClass[i] == N) { bFound = true; break; }
		if (bFound || SeenCount >= 512)
			continue;
		SeenClass[SeenCount++] = N;
		Con.DDLog("CLASS", "name=" $ N $ "|proj=" $ A.IsA('Projectile') $ "|fx=" $ A.IsA('Effects') $ "|owner=" $ ActorName(A.Owner)
			$ "|instigator=" $ ActorName(A.Instigator) $ "|role=" $ A.Role);
	}
}

function string VF(vector X)
{
	return X.X $ "," $ X.Y $ "," $ X.Z;
}

// ZeroPing (zp_ShockRifle, also the ComboGib rifle) draws the recorder's own beam twice in a client demo, and both
// copies are broken in playback:
//  * the locally predicted beam is recorded with its location only (no rotation, MoveAmount or NumPuffs): one stray
//    segment along the world X axis, wherever the player aimed;
//  * the server's copy (Owner = shooter, bOwnerNoSee) has the right data, but zp_ShockBeam.Timer does not continue the
//    chain while the owner is the autonomous proxy (= the recorder in his own demo), and uDemo hides it in first person.
// Fix: hide the stray, and take the server's copy away from its owner before its first Timer, so the mod's own code
// draws the whole beam and no view hides it. Must run after ActorPass (SHOT lines need the owner).
function bool BeamOfRecorder(Actor A)
{
	return A.bOwnerNoSee && Pawn(A.Owner) != None && A.Owner.Role == ROLE_AutonomousProxy;
}

function BeamFixLog(string What, Actor A)
{
	if (bBeamLog)
		Con.DDLog("BEAMFIX", What $ "=" $ A.Name $ "|loc=" $ V(A.Location));
}

function HideStray(Actor A)
{
	A.bHidden = true;
	A.DrawType = DT_None;
	BeamFixLog("hide", A);
}

function BeamFix()
{
	local ShockBeam B;
	local SuperShockBeam SB;
	foreach AllActors(class'ShockBeam', B)
	{
		if (B.Role == ROLE_Authority)        // chain segments spawned on this machine
			continue;
		if (B.Owner == None)
		{
			if (!B.bHidden && B.NumPuffs == 0 && B.MoveAmount == vect(0,0,0) && B.Rotation.Pitch == 0 && B.Rotation.Yaw == 0)
				HideStray(B);
		}
		else if (BeamOfRecorder(B))
		{
			BeamFixLog("free", B);
			B.SetOwner(None);
		}
	}
	foreach AllActors(class'SuperShockBeam', SB)   // instagib
	{
		if (SB.Role == ROLE_Authority)
			continue;
		if (SB.Owner == None)
		{
			if (!SB.bHidden && SB.NumPuffs == 0 && SB.MoveAmount == vect(0,0,0) && SB.Rotation.Pitch == 0 && SB.Rotation.Yaw == 0)
				HideStray(SB);
		}
		else if (BeamOfRecorder(SB))
		{
			BeamFixLog("free", SB);
			SB.SetOwner(None);
		}
	}
}

// Logs every Effects actor once (FX) and every shock beam again whenever its direction / chain data changes (BEAM).
function BeamLog()
{
	local Effects E;
	local ShockBeam B;
	local int i, Slot;
	local string Sig;
	foreach AllActors(class'Effects', E)
	{
		Slot = -1;
		for (i = 0; i < 128; i++)
			if (BeamLogSeen[i] == E) { Slot = i; break; }
		B = ShockBeam(E);
		if (B != None)
			Sig = (B.Rotation.Pitch & 65535) $ "," $ (B.Rotation.Yaw & 65535) $ "|move=" $ VF(B.MoveAmount) $ "|puffs=" $ B.NumPuffs
				$ "|hid=" $ B.bHidden;
		else
			Sig = "";
		if (Slot >= 0 && (B == None || BeamLogSig[Slot] == Sig))
			continue;
		if (Slot < 0)
		{
			Slot = BeamLogPos;
			BeamLogSeen[Slot] = E;
			BeamLogPos = (BeamLogPos + 1) % 128;
			Con.DDLog("FX", "class=" $ E.Class $ "|name=" $ E.Name $ "|role=" $ int(E.Role) $ "|rrole=" $ int(E.RemoteRole)
				$ "|owner=" $ ActorName(E.Owner) $ "|loc=" $ VF(E.Location)
				$ "|rot=" $ (E.Rotation.Pitch & 65535) $ "," $ (E.Rotation.Yaw & 65535)
				$ "|nosee=" $ E.bOwnerNoSee $ "|hid=" $ E.bHidden $ "|life=" $ E.LifeSpan);
		}
		BeamLogSig[Slot] = Sig;
		if (B != None)
			Con.DDLog("BEAM", "name=" $ B.Name $ "|rot=" $ Sig $ "|timer=" $ B.TimerRate $ "," $ B.TimerCounter
				$ "|life=" $ B.LifeSpan $ "|phys=" $ int(B.Physics));
	}
}

function bool ProbeKnown(Actor A)
{
	local int i;
	for (i = 0; i < 32; i++)
		if (ProbeSeen[i] == A)
			return true;
	return false;
}

function Probe()
{
	local Pawn P;
	local Carcass C;
	local int Id;
	foreach AllActors(class'Pawn', P)
	{
		if (P.PlayerReplicationInfo == None || P.IsA('Spectator') || P.IsA('DemoPlaybackSpec'))
			continue;
		Id = P.PlayerReplicationInfo.PlayerID;
		if (Id != ProbeK && Id != ProbeV)
			continue;
		if (Id == ProbeV)
			ProbeVLoc = P.Location;
		Con.DDLog("PROBE", "id=" $ Id $ "|loc=" $ VF(P.Location) $ "|vel=" $ VF(P.Velocity) $ "|rot=" $ P.Rotation.Pitch $ "," $ P.Rotation.Yaw
			$ "|vr=" $ P.ViewRotation.Pitch $ "," $ P.ViewRotation.Yaw $ "|hid=" $ P.bHidden $ "|hp=" $ P.Health
			$ "|ch=" $ P.CollisionHeight $ "|eye=" $ P.EyeHeight $ "|base=" $ P.BaseEyeHeight $ "|anim=" $ P.AnimSequence
			$ "|wep=" $ P.Weapon $ "|fov=" $ P.FOVAngle $ "|deaths=" $ int(P.PlayerReplicationInfo.Deaths));
	}
	foreach AllActors(class'Carcass', C)
		if (VSize(C.Location - ProbeVLoc) < 600 && !ProbeKnown(C))
		{
			ProbeSeen[ProbePos] = C;
			ProbePos = (ProbePos + 1) % 32;
			Con.DDLog("CARC", "class=" $ C.Class.Name $ "|loc=" $ VF(C.Location) $ "|vel=" $ VF(C.Velocity) $ "|anim=" $ C.AnimSequence
				$ "|mesh=" $ C.Mesh);
		}
}

event Tick(float DeltaTime)
{
	local DemoPlaybackSpec S;
	// (windows opened with bQuickKeyEnable leave bUWindowActive false: check the console state too)
	if (Con.bAutoClose && (Con.bUWindowActive || Con.IsInState('UWindow')))
	{
		Con.CloseUWindow();
		Con.DDLog("WIN", "closed a window opened by the demo");
	}
	ScanScores();
	UpdatePawnCache();
	UpdateHud();
	ApplyRamp(false);
	S = Spec();
	if (bProbe && (S == None || !S.bSeeking))
		Probe();
	if (bBeamLog && (S == None || !S.bSeeking))
		BeamLog();              // before BeamFix: logs the actors as the demo delivers them
	if ((bRich || bNoGore) && (S == None || !S.bSeeking))
		ActorPass();
	if (bBeamFix)
		BeamFix();
	if (bRich && (S == None || !S.bSeeking))
	{
		if (!bBasesLogged)
			LogBases();
		PosAccum += DeltaTime;
		if (PosAccum >= PosInterval)
		{
			PosAccum = 0;
			LogPids();
			LogPositions();
		}
	}
	if (bCensus)
	{
		CensusAccum += DeltaTime;
		if (CensusAccum > 0.05) { CensusAccum = 0; Census(); }
	}
	Accum += DeltaTime;
	if (Accum >= ReportInterval)
	{
		Accum = 0;
		ReportState("STATE");
	}
}

defaultproperties
{
	ReportInterval=0.5
	PosInterval=0.25
	bBeamFix=True
	RemoteRole=ROLE_None
	bAlwaysTick=True
}
