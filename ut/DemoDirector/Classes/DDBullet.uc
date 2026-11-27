//=============================================================================
// DDBullet - visible sniper bullet for bullet-time shots. UT's sniper rifle is hitscan: there is no projectile in
// the game or in the demo, so this actor flies from the shooter to the victim's head while the demo crawls
// (ddramp ~0.02x) and arrives exactly at the demo time of the kill.
//
//   ddbullet from=x,y,z to=x,y,z tk=<demo time of the kill> dur=<wall seconds of flight> ...
//   ddbullet off
//     slow0  wall seconds of slow flight at the start (leaving the barrel), default 0
//     slow1  wall seconds of slow flight at the end (arriving at the head), default 0
//     ws     speed in the slow parts relative to the cruise speed, default 0.06
//     scale  bullet size (1 = 5 uu long), default 1        spin   deg/s (wall), default 1440
//     rings  distance between air ripples (uu), 0 = none   rs     ripple end size, default 1   rg  ripple brightness
//     wake   distance between vapour puffs (uu), 0 = none
//     gore   gore bursts at the impact (0 = none, 1 = the mod's normal headshot, 2 = double ...). The gore comes from
//            an optional provider class (gorefx=, default DDUltraGore.DDUltraGoreFX = Ultra Gore SSE, see DDGoreBase);
//            without it the impact gets stock UT blood
//     vid kid  PlayerIDs of victim / killer (gore colour and size, kill credit)
//     mom    gore momentum along the shot (uu/s), default 350 (= sniper headshot momentum / mass)
//     blood  auto = the mod's blood colour per model (Boss/Xan = silver); default is always red
//     track  1 (default) = the end point follows the victim pawn (vid) to where its head will be at tk; hz = head height
//     explode 1 (default) = hide UT's intact flying head, the head bursts into skull fragments; skull = extra bone bursts
//     fog / splat = size of the mod's blood fog / splat sprites (0.35 / 0.55; fog=0 = none)
//
// Time base: wall seconds until tk, from the speed ramp (DDWatcher.WallBetween). Demo time moves in steps at 0.02x,
// so between steps the bullet runs on real time, held within [TD, TD + 0.3] (same trick as DDCam).
// Logs DD|BULLET|launch and DD|BULLET|hit.
//=============================================================================
class DDBullet extends Effects;

#exec MESH IMPORT MESH=DDBulletM ANIVFILE=MODELS\ddbullet_a.3d DATAFILE=MODELS\ddbullet_d.3d X=0 Y=0 Z=0
#exec MESH ORIGIN MESH=DDBulletM X=0 Y=0 Z=0
#exec MESH SEQUENCE MESH=DDBulletM SEQ=All STARTFRAME=0 NUMFRAMES=1
#exec TEXTURE IMPORT NAME=DDBulletTex FILE=TEXTURES\ddbullet.bmp GROUP=Skins
#exec TEXTURE IMPORT NAME=DDShineTex FILE=TEXTURES\ddshine.bmp GROUP=Skins
#exec MESHMAP NEW MESHMAP=DDBulletM MESH=DDBulletM
#exec MESHMAP SCALE MESHMAP=DDBulletM X=0.003125 Y=0.003125 Z=0.00625
#exec MESHMAP SETTEXTURE MESHMAP=DDBulletM NUM=1 TEXTURE=DDBulletTex

var DDConsole Con;
var bool bArmed, bLaunched, bHit, bGone;
var vector P0, P1, Dir;
var float PathLen, EndDist;
var float TK, Dur, T;
var float Slow0, Slow1, WS;
var float G[65];             // distance fraction over time fraction (slow start / cruise / slow end)
var float BScale, Spin, RingGap, RingSize, RingGlow, WakeGap, NextRing, NextWake, GoreMom;
var int GoreN, Vid, Kid;
var bool bAutoBlood;
var vector P1Plan;           // planned head position (to=)
var float HeadZ;             // head height above the victim's Location (hz=, default 30)
var bool bTrack;             // re-aim at the victim pawn every tick (track=0 turns it off)
var float TrackErr;
var float FogScale, SplatScale;   // size of the mod's blood fog / splat sprites (they hid the head), fog= splat=
var int SkullN;              // extra skull-fragment bursts (10 bone pieces each), skull=
var bool bHeadPop;           // explode=1: hide UT's intact flying head (UTHeads) so the head bursts instead
var int HeadsHidden;
var Carcass Body;            // the victim's corpse after the hit; kept in UT's headless death pose
var name BodyAnim;
var int BodyForced;
var DDBulletShine Shine;
var DDGoreBase Gore;        // gore provider, loaded by name (gorefx=), see DDGoreBase.uc
var bool bGoreTried;
var string GoreClass;

function vector ParseVec(string S)
{
	local vector V;
	local int i;
	i = InStr(S, ","); V.X = float(Left(S, i)); S = Mid(S, i + 1);
	i = InStr(S, ","); V.Y = float(Left(S, i)); V.Z = float(Mid(S, i + 1));
	return V;
}

function string Arg(string S, string Key)
{
	local int i, j;
	S = " " $ S $ " ";
	i = InStr(S, " " $ Key $ "=");
	if (i < 0)
		return "";
	S = Mid(S, i + Len(Key) + 2);
	j = InStr(S, " ");
	return Left(S, j);
}

function float FArg(string S, string Key, float Def)
{
	local string V;
	V = Arg(S, Key);
	if (V == "")
		return Def;
	return float(V);
}

function float Smooth(float X)
{
	X = FClamp(X, 0, 1);
	return X * X * (3 - 2 * X);
}

// relative speed at time fraction U: slow for Slow0 seconds, cruise, slow for the last Slow1 seconds
function float SpeedW(float U)
{
	local float W, A, B;
	W = 1;
	A = Slow0 / Dur;
	B = Slow1 / Dur;
	if (A > 0)
		W *= WS + (1 - WS) * Smooth((U - A * 0.65) / (A * 0.35));
	if (B > 0)
		W *= WS + (1 - WS) * (1 - Smooth((U - (1 - B)) / (B * 0.35)));
	return W;
}

function BuildTable()
{
	local int i;
	local float Sum;
	G[0] = 0;
	for (i = 1; i <= 64; i++)
	{
		Sum += SpeedW((i - 0.5) / 64.0);
		G[i] = Sum;
	}
	for (i = 1; i <= 64; i++)
		G[i] = G[i] / Sum;
}

function float DistFrac(float U)
{
	local int i;
	local float X;
	if (U <= 0) return 0;
	if (U >= 1) return 1 + (U - 1) * (G[64] - G[63]) * 64;   // beyond the head: keep the final speed
	X = U * 64;
	i = int(X);
	return G[i] + (G[i + 1] - G[i]) * (X - i);
}

function Configure(string S)
{
	local vector HL, HN;
	if (S == "" || S ~= "off" || Arg(S, "from") == "" || Arg(S, "to") == "")
	{
		Disarm();
		return;
	}
	P0 = ParseVec(Arg(S, "from"));
	P1 = ParseVec(Arg(S, "to"));
	Dir = Normal(P1 - P0);
	PathLen = VSize(P1 - P0);
	TK = FArg(S, "tk", 0);
	Dur = FMax(FArg(S, "dur", 4), 0.1);
	Slow0 = FClamp(FArg(S, "slow0", 0), 0, Dur * 0.45);
	Slow1 = FClamp(FArg(S, "slow1", 0), 0, Dur * 0.45);
	WS = FClamp(FArg(S, "ws", 0.06), 0.005, 1);
	BScale = FArg(S, "scale", 1);
	Spin = FArg(S, "spin", 1440);
	RingGap = FArg(S, "rings", 70);
	RingSize = FArg(S, "rs", 1);
	RingGlow = FArg(S, "rg", 0.6);
	WakeGap = FArg(S, "wake", 0);
	GoreN = int(FArg(S, "gore", 1));
	GoreMom = FArg(S, "mom", 350);
	FogScale = FArg(S, "fog", 0.35);
	SplatScale = FArg(S, "splat", 0.55);
	SkullN = int(FArg(S, "skull", 1));
	bHeadPop = FArg(S, "explode", 1) != 0;
	if (Arg(S, "gorefx") != "" && Arg(S, "gorefx") != GoreClass)
	{
		GoreClass = Arg(S, "gorefx");
		bGoreTried = false;
		if (Gore != None) Gore.Destroy();
		Gore = None;
	}
	HeadsHidden = 0;
	Body = None;
	BodyForced = 0;
	bAutoBlood = Arg(S, "blood") ~= "auto";
	P1Plan = P1;
	HeadZ = FArg(S, "hz", 30);
	bTrack = FArg(S, "track", 1) != 0;
	TrackErr = 0;
	Vid = int(FArg(S, "vid", -1));
	Kid = int(FArg(S, "kid", -1));
	BuildTable();
	// the bullet flies on behind the head until it meets a wall
	if (Trace(HL, HN, P1 + Dir * 4000, P1 + Dir * 20, false) != None)
		EndDist = PathLen + VSize(HL - P1);
	else
		EndDist = PathLen + 4000;
	bArmed = true; bLaunched = false; bHit = false; bGone = false;
	T = 0;
	DrawScale = BScale;
	Place(0);
	Show(false);
	Con.DDLog("BULLET", "armed|len=" $ PathLen $ "|tk=" $ TK $ "|dur=" $ Dur $ "|args=" $ S);
}

function Disarm()
{
	bArmed = false;
	Show(false);
	if (Con != None)
		Con.DDLog("BULLET", "off");
}

function Show(bool bOn)
{
	bHidden = !bOn;
	if (Shine == None)
		Shine = Spawn(class'DDBulletShine');
	if (Shine != None)
		Shine.bHidden = !bOn;
}

function Place(float Dist)
{
	local rotator R;
	SetLocation(P0 + Dir * Dist);
	R = rotator(Dir);
	R.Roll = int(Spin * T * 182.044) & 65535;
	SetRotation(R);
	if (Shine != None)
	{
		Shine.SetLocation(Location);
		R.Roll = 0;
		Shine.SetRotation(R);
		Shine.DrawScale = BScale * 1.04;
	}
}

function Ripple(vector Loc, float Size, float Life, float Glow)
{
	local DDRing Rg;
	Rg = Spawn(class'DDRing',,, Loc, rotator(Dir));
	if (Rg != None)
		Rg.Setup(Life, 0.25 * Size, 2.6 * Size, Glow, false);
}

// The planned head position comes from a probe run; the pawn shown in THIS playback can be tens of uu away from it
// (extrapolation between position updates). So the end point follows the victim pawn: where its head will be at TK.
function Track(float Now)
{
	local Pawn V;
	local vector Want;
	V = AnyPawn(Vid);
	if (V == None || V.bHidden)
		return;
	Want = V.Location + V.Velocity * FMax(TK - Now, 0) + vect(0,0,1) * HeadZ;
	if (VSize(Want - P1Plan) > 300)
		return;                          // not the pawn we planned for (respawned elsewhere)
	TrackErr = VSize(Want - P1Plan);
	P1 += (Want - P1) * 0.25;
	Dir = Normal(P1 - P0);
	PathLen = VSize(P1 - P0);
}

function string VictimInfo()
{
	local Pawn V;
	V = AnyPawn(Vid);
	if (V == None)
		return "victim=None";
	return "vloc=" $ V.Location $ "|vhid=" $ V.bHidden $ "|vstyle=" $ V.Style $ "|vdraw=" $ V.DrawType $ "|vglow=" $ V.ScaleGlow
		$ "|vmesh=" $ V.Mesh $ "|venv=" $ V.bMeshEnviroMap;
}

function Pawn AnyPawn(int Id)
{
	local Pawn P;
	if (Id < 0)
		return None;
	foreach AllActors(class'Pawn', P)
		if (P.PlayerReplicationInfo != None && P.PlayerReplicationInfo.PlayerID == Id
			&& !P.IsA('Spectator') && !P.IsA('DemoPlaybackSpec'))
			return P;
	return None;
}

// Only kills with damage type 'Decapitated' make UT play its headless death pose (male/Xan 'Dead4', female 'Dead6':
// the head vertices collapse into the neck). Most of the demo kills used other death animations, so the corpse kept
// its head after our burst. Find the victim's corpse and keep it in the headless pose (re-applied every tick).
function KeepHeadless()
{
	local Carcass C, Best;
	local float D, BestD;
	if (Body == None || Body.bDeleteMe)
	{
		Body = None;
		BestD = 160;
		foreach RadiusActors(class'Carcass', C, 160, P1)
			if (C.IsA('UTHumanCarcass') && !C.bHidden)
			{
				D = VSize(C.Location + vect(0,0,30) - P1);
				if (D < BestD) { BestD = D; Best = C; }
			}
		if (Best == None)
			return;
		Body = Best;
		if (InStr(Caps(string(Body.Mesh)), "TSKM") >= 0)
			BodyAnim = 'Dead5';      // Skaarj trooper (MultiMesh.TSkaarj.PlaySkaarjDecap)
		else if (Body.HasAnim('Dead6'))
			BodyAnim = 'Dead6';      // female meshes (TournamentFemale.PlayDecap)
		else
			BodyAnim = 'Dead4';      // male and Xan meshes (TournamentMale.PlayDecap)
		Con.DDLog("GORE", "body=" $ Body.Class.Name $ "|was=" $ Body.AnimSequence $ "|now=" $ BodyAnim $ "|mesh=" $ Body.Mesh);
	}
	if (Body.AnimSequence != BodyAnim)
	{
		Body.PlayAnim(BodyAnim, 1.0, 0.0);
		BodyForced++;
		if (BodyForced > 1 && BodyForced < 6)
			Con.DDLog("GORE", "body re-forced " $ BodyForced);
	}
}

// UT99's own decapitation throws the whole head off intact (UT_HeadMale etc., carcass anim Dead4 is headless).
// Hide it near the impact so the head bursts into the mod's skull fragments instead.
function HideHeads()
{
	local Carcass C;
	foreach RadiusActors(class'Carcass', C, 300, P1)
		if ((C.IsA('UTHeads') || (InStr(Caps(string(C.Class.Name)), "HEAD") >= 0 && !C.IsA('UTHumanCarcass'))) && !C.bHidden)
		{
			C.bHidden = true;
			C.DrawType = DT_None;
			HeadsHidden++;
			Con.DDLog("GORE", "headhidden=" $ C.Class.Name $ "|at=" $ C.Location);
		}
}

function UltraGore()
{
	local Pawn V, K;
	local class<DDGoreBase> GC;
	V = AnyPawn(Vid);
	K = AnyPawn(Kid);
	if (Gore == None && !bGoreTried)
	{
		bGoreTried = true;
		GC = class<DDGoreBase>(DynamicLoadObject(GoreClass, class'Class', true));
		if (GC != None)
			Gore = Spawn(GC);
		Con.DDLog("GORE", "provider=" $ GoreClass $ "|loaded=" $ (Gore != None));
	}
	if (Gore == None || !Gore.Burst(self, V, K))
	{
		Spawn(class'UT_BigBloodHit',,, P1, rotator(-Dir));   // stock UT blood (no gore mod installed)
		Con.DDLog("GORE", "stock|at=" $ P1);
	}
	if (bHeadPop)
		HideHeads();
}

event Tick(float DeltaTime)
{
	local DemoPlaybackSpec S;
	local float Now, Rem, TD, dt, D;
	local int n;
	local vector HL, HN;

	if (!bArmed || Con == None || Con.Watcher == None)
		return;
	S = Con.Watcher.Spec();
	if (S == None || S.bSeeking)
		return;
	Now = Con.Watcher.DemoTime();
	if (Now < TK)
	{
		if (Con.Watcher.RampN > 0)
			Rem = Con.Watcher.WallBetween(Now, TK);
		else if (S.Driver != None && S.Driver.mySpeed > 0)
			Rem = (TK - Now) / S.Driver.mySpeed;
		else
			Rem = TK - Now;
	}
	TD = Dur - Rem;
	if (TD < 0)
	{
		// before the launch (also after a seek back): wait hidden at the muzzle
		if (bLaunched || !bHidden)
		{
			bLaunched = false; bHit = false; bGone = false;
			T = 0;
			Place(0);
			Show(false);
		}
		return;
	}
	dt = DeltaTime;
	if (Level.TimeDilation > 0)
		dt = DeltaTime / Level.TimeDilation;
	if (!bLaunched)
	{
		bLaunched = true;
		T = TD;
		NextRing = 6;
		NextWake = 0;
		Show(true);
		Con.DDLog("BULLET", "launch|td=" $ TD);
	}
	else if (bHit)
		T += dt;                     // after the impact: free run (flies on to the wall behind)
	else
		T = FClamp(T + dt, TD, TD + 0.3);
	if (Now >= TK && T < Dur)
		T = Dur;                     // the kill is in the demo: never arrive late
	if (bHit && bHeadPop && Now < TK + 1.5)
		HideHeads();                 // the head chunk can arrive a demo frame after our impact
	if (bHit && bHeadPop)
		KeepHeadless();              // the whole time after the hit: the head stays gone
	if (bGone)
		return;
	if (bTrack && !bHit)
		Track(Now);

	D = PathLen * DistFrac(T / Dur);
	if (!bHit && T >= Dur)
	{
		bHit = true;
		D = FMax(D, PathLen);
		if (Trace(HL, HN, P1 + Dir * 4000, P1 + Dir * 20, false) != None)
			EndDist = PathLen + VSize(HL - P1);
		else
			EndDist = PathLen + 4000;
		Ripple(P1, 3.0 * RingSize, 1.0, 0.8);
		Con.DDLog("BULLET", "hit|T=" $ T $ "|demo=" $ Now $ "|at=" $ P1 $ "|plan=" $ P1Plan $ "|trackerr=" $ TrackErr $ "|" $ VictimInfo());
		if (GoreN > 0)
			UltraGore();
	}
	if (D >= EndDist)
	{
		bGone = true;
		Show(false);
		return;
	}
	Place(D);
	// air ripples and vapour trail by distance (at most a few per tick)
	if (RingGap > 0 && !bHit)
	{
		n = 0;
		while (D >= NextRing && n < 4)
		{
			Ripple(P0 + Dir * NextRing, RingSize, 1.25, RingGlow);
			NextRing += RingGap;
			n++;
		}
		if (D >= NextRing)
			NextRing = D + RingGap;
	}
	if (WakeGap > 0)
	{
		n = 0;
		while (D >= NextWake && n < 8)
		{
			Puff(P0 + Dir * NextWake);
			NextWake += WakeGap;
			n++;
		}
		if (D >= NextWake)
			NextWake = D + WakeGap;
	}
}

function Puff(vector Loc)
{
	local DDRing Rg;
	Rg = Spawn(class'DDRing',,, Loc);
	if (Rg != None)
		Rg.Setup(0.9, 0.07 * BScale, 0.16 * BScale, 0.55, true);
}

defaultproperties
{
	DrawType=DT_Mesh
	Mesh=LodMesh'DemoDirector.DDBulletM'
	bUnlit=True
	AmbientGlow=0
	ScaleGlow=1.0
	RemoteRole=ROLE_None
	bAlwaysTick=True
	Physics=PHYS_None
	LifeSpan=0
	bHidden=True
	bCollideActors=False
	bCollideWorld=False
	Dur=4
	BScale=1
	GoreClass="DDUltraGore.DDUltraGoreFX"
}
