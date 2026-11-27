//=============================================================================
// DDCam - scripted cinematic camera for demo playback (free-cam mode of uDemo).
// Drives the demo spectator's Location/ViewRotation every tick.
//
// Configure with the console command:  ddcam mode=orbit tgt=12 r=320 h=90 a0=40 w=22 ...
//   mode   off | orbit | dolly | chase | follow | ball | static | fly | dive | bullet
//   bullet rig fixed to the bullet-time bullet (DDBullet): dist= behind it (negative = ahead), r= away from the flight
//          axis at angle a0 (+ w deg/s; 0 = right, 90 = above), h= extra height, lead= look-ahead (0 = at the bullet).
//          The rig can change during the flight: dist1 r1 a1 lead1 h1 fov1 = values at flight time fraction um (0.5),
//          dist2 r2 a2 lead2 h2 fov2 = values at the impact. After the impact it stays at the head and backs off
//          by pull= uu (the Ultra Gore blood fog fills the frame from close up).
//   lookb  1 = any other mode looks at the bullet (pan with it from a fixed spot, dolly, fly)
//   follow like chase but behind the smoothed direction of travel; side= sideways offset, lead= look-ahead,
//          look=<other id> frames the midpoint of both players
// Used alone (ddcam) or as one rig of a one-take timeline (ddtake, see DDTake.uc); a rig whose target is dead
// holds its last framing.
//   tgt    PlayerID to follow/orbit/look at          look  PlayerID to look at (default tgt)
//   p      x,y,z  center (orbit without tgt) / start (dolly) / position (static)
//   p2     x,y,z  dolly end position                 at    x,y,z fixed look-at point
//   r h    orbit radius / height (uu)               a0 w  start angle (deg) / angular speed (deg/s)
//   dist   chase / ball distance behind             dur   dolly duration (s)
//   fov    field of view (deg)                      fov2  fov at the end of dur (zoom)
//   lag    position smoothing 0 (none) .. 0.95      off   z offset of the look-at point
//   ballby PlayerID whose next shock ball is followed (mode=ball)
//   bp     x,y,z launch point of the wanted ball: the nearest ball (< 450 uu) is taken, never an older one
//   fly    spline through p, p2 (,p3 ,p4) over dur (eased), looking at `at`, `look` or along the path
//   path   dense keys loaded with "ddpath clear" / "ddpath add p= at= fov=" (tools\mapgen\cam_path.py), one every
//          kdt= s (0.1): Catmull-Rom through them, no smoothing, no pull-in at walls (checked offline per frame)
//   dive   from p toward `at`, accelerating (u^2.5) over dur, stops 16 uu short of `at`; fov -> fov2
//   roll   camera roll speed (deg/s), fly and dive only
//   rt     1 = camera time runs in real time (bullet time in slow motion), 0 = demo time
//   dt0    demo time at which the move starts (camera holds its start pose before)
// All motion uses smooth easing; the camera is pulled in front of walls with a trace.
//=============================================================================
class DDCam extends Info;

var DDConsole Con;
var bool bActive;
var string Mode;
var int Tgt, LookId, BallBy;
var vector P1, P2, At, P3, P4;
var bool bHasP1, bHasP2, bHasAt, bHasP3, bHasP4;
var float RollW;
var float R, H, A0, W, Dist, Dur, Fov, Fov2, Lag, ZOff;
var bool bRealTime;
var float T;                // camera time since configure
var vector CamLoc, LookLoc; // current smoothed values
var bool bInit;
var Projectile Ball;
var vector BallLastLoc, BallLastDir;
var vector BP;              // ball mode: launch point of the wanted ball ("bp=x,y,z"), picks the nearest one
var bool bHasBP;
var float StartDemoT;       // dt0
var bool bSlave;            // owned by DDTake: computes only, never applies the view itself
var float CurFovOut;
var vector FollowDir;       // follow mode: smoothed direction of travel
var float Side, Lead;       // follow mode: sideways offset / look-ahead (uu)
var float FollowOff, FollowOffWant;   // follow mode: current / wanted swing around the player (deg)
var vector LastTgtLoc;
var float WideW;            // wide= : half width of the clearance check (orbit, follow); 0 = single sight line
var int CurRollOut;
var bool bLookB;            // lookb=1: look at the bullet-time bullet (any mode)
var float BK[18];           // bullet mode keys (start, mid, end) x (dist, r, a, lead, h, fov)
var bool bHasK1;
var float UM, UE;           // bullet mode: flight fraction of the middle key / of the end key (ue<1 = settle before the hit)
var float Pull;             // bullet mode: extra distance from the head after the impact (eases in over ~1.5 s)
var float LookZ2;           // bullet mode: look-at z offset at the impact (lz2=, eases in over the last 30% of the flight)
var vector PathP[600], PathA[600];   // path mode: camera / look-at keys every PathDT seconds ("ddpath add ...")
var float PathF[600];       // path mode: fov per key
var float PathR[600];       // path mode: camera roll per key (deg): e.g. to read a ceiling emblem upright
var int PathN;
var float PathDT, PathFov, PathRoll;
// path mode frame-stepped rendering ("ddpath render fps=60 from=0 to=12"): the camera time is set per frame and
// every frame is saved with "shot", so the motion is exactly even whatever the game's frame rate or the demo's clock
// (an empty-map demo only advances its clock in jumps, which made live captures move in bursts)
var bool bStep;
var float StepT, StepDT, StepEnd;
var int StepWait, StepCount;

function vector ParseVec(string S)
{
	local vector V;
	local int i;
	i = InStr(S, ","); V.X = float(Left(S, i)); S = Mid(S, i + 1);
	i = InStr(S, ","); V.Y = float(Left(S, i)); V.Z = float(Mid(S, i + 1));
	return V;
}

// Returns value of key in "k1=v1 k2=v2"; "" if missing.
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

function Configure(string S)
{
	local string V;
	V = Arg(S, "mode");
	if (V == "" || V ~= "off")
	{
		StopCam();
		return;
	}
	Mode = Caps(V);
	Tgt = int(FArg(S, "tgt", -1));
	LookId = int(FArg(S, "look", Tgt));
	BallBy = int(FArg(S, "ballby", Tgt));
	bHasP1 = Arg(S, "p") != "";  if (bHasP1) P1 = ParseVec(Arg(S, "p"));
	bHasP2 = Arg(S, "p2") != ""; if (bHasP2) P2 = ParseVec(Arg(S, "p2"));
	bHasAt = Arg(S, "at") != ""; if (bHasAt) At = ParseVec(Arg(S, "at"));
	bHasP3 = Arg(S, "p3") != ""; if (bHasP3) P3 = ParseVec(Arg(S, "p3"));
	bHasP4 = bHasP3 && Arg(S, "p4") != ""; if (bHasP4) P4 = ParseVec(Arg(S, "p4"));
	RollW = FArg(S, "roll", 0);
	bHasBP = Arg(S, "bp") != ""; if (bHasBP) BP = ParseVec(Arg(S, "bp"));
	BallLastDir = vect(0,0,0); BallLastLoc = vect(0,0,0);   // no stale ball from a previous shot (-Reuse)
	R = FArg(S, "r", 320); H = FArg(S, "h", 90); A0 = FArg(S, "a0", 0); W = FArg(S, "w", 20);
	Dist = FArg(S, "dist", 220); Dur = FArg(S, "dur", 4); Fov = FArg(S, "fov", 90); Fov2 = FArg(S, "fov2", Fov);
	Lag = FClamp(FArg(S, "lag", 0.85), 0, 0.98); ZOff = FArg(S, "off", 25);
	bRealTime = FArg(S, "rt", 1) != 0;
	Side = FArg(S, "side", 0); Lead = FArg(S, "lead", 150); FollowDir = vect(0,0,0);
	FollowOff = 0; FollowOffWant = 0;
	WideW = FArg(S, "wide", 0);
	bLookB = FArg(S, "lookb", 0) != 0;
	if (Mode == "BULLET")
	{
		if (Arg(S, "off") == "") ZOff = 0;
		if (Arg(S, "w") == "") W = 0;
		BK[0] = FArg(S, "dist", 0); BK[1] = FArg(S, "r", 0); BK[2] = FArg(S, "a0", 0);
		BK[3] = FArg(S, "lead", 0); BK[4] = FArg(S, "h", 0); BK[5] = FArg(S, "fov", 90);
		bHasK1 = (Arg(S, "dist1") $ Arg(S, "r1") $ Arg(S, "a1") $ Arg(S, "lead1") $ Arg(S, "h1") $ Arg(S, "fov1")) != "";
		BK[6] = FArg(S, "dist1", BK[0]); BK[7] = FArg(S, "r1", BK[1]); BK[8] = FArg(S, "a1", BK[2]);
		BK[9] = FArg(S, "lead1", BK[3]); BK[10] = FArg(S, "h1", BK[4]); BK[11] = FArg(S, "fov1", BK[5]);
		BK[12] = FArg(S, "dist2", BK[6]); BK[13] = FArg(S, "r2", BK[7]); BK[14] = FArg(S, "a2", BK[8]);
		BK[15] = FArg(S, "lead2", BK[9]); BK[16] = FArg(S, "h2", BK[10]); BK[17] = FArg(S, "fov2", BK[11]);
		UM = FClamp(FArg(S, "um", 0.5), 0.02, 0.98);
		UE = FClamp(FArg(S, "ue", 1), UM + 0.01, 1);
		Pull = FArg(S, "pull", 0);
		LookZ2 = FArg(S, "lz2", 0);
		Fov2 = Fov;
	}
	else if (bLookB && Arg(S, "off") == "")
		ZOff = 0;
	if (Mode == "PATH")
	{
		// keys are exact (planned and clearance-checked offline): no smoothing, no look-at offset unless asked
		PathDT = FMax(FArg(S, "kdt", 0.1), 0.001);
		if (Arg(S, "lag") == "") Lag = 0;
		if (Arg(S, "off") == "") ZOff = 0;
	}
	T = 0; bInit = false; Ball = None;
	StartDemoT = FArg(S, "dt0", Con.Watcher.DemoTime());
	bActive = true;
	Con.DDLog("CAM", "mode=" $ Mode $ "|tgt=" $ Tgt $ "|args=" $ S);
}

function StopCam()
{
	local PlayerPawn S;
	bActive = false;
	S = Con.Viewport.Actor;
	if (S != None)
	{
		S.DesiredFOV = S.DefaultFOV;
		S.FOVAngle = S.DefaultFOV;
	}
	Con.DDLog("CAM", "mode=off");
}

function Pawn FindPawn(int Id)
{
	local Pawn P;
	if (Id < 0)
		return None;
	foreach AllActors(class'Pawn', P)
		if (P.PlayerReplicationInfo != None && P.PlayerReplicationInfo.PlayerID == Id && P.Health > 0
			&& !P.IsA('Spectator') && !P.IsA('DemoPlaybackSpec'))
			return P;
	return None;
}

function float Ease(float X)
{
	X = FClamp(X, 0, 1);
	return X * X * (3 - 2 * X);   // smoothstep
}

// bullet mode: value of parameter i at bullet progress U (start -> [mid at UM] -> end, eased)
function float BKey(int i, float U)
{
	if (!bHasK1)
		return BK[i] + (BK[12 + i] - BK[i]) * Ease(U / UE);
	if (U < UM)
		return BK[i] + (BK[6 + i] - BK[i]) * Ease(U / UM);
	return BK[6 + i] + (BK[12 + i] - BK[6 + i]) * Ease((U - UM) / (UE - UM));
}

// "ddpath render fps=60 from=0 to=12 wait=3": render every frame from..to with a screenshot each (see Tick)
function StartRender(string S)
{
	StepDT = 1.0 / FMax(FArg(S, "fps", 60), 1);
	StepT = FArg(S, "from", 0);
	StepEnd = FArg(S, "to", StepT);
	StepWait = int(FArg(S, "wait", 3));      // let the first frames settle (view, textures) before the first shot
	StepCount = 0;
	bStep = true;
	Con.DDLog("PATH", "render from=" $ StepT $ "|to=" $ StepEnd $ "|dt=" $ StepDT);
}

// path mode keys: "ddpath clear", "ddpath add p=x,y,z at=x,y,z fov=f" (one key per command; up to 600)
function PathAdd(string S)
{
	if (PathN >= 600)
		return;
	PathP[PathN] = ParseVec(Arg(S, "p"));
	PathA[PathN] = ParseVec(Arg(S, "at"));
	PathF[PathN] = FArg(S, "fov", 90);
	PathR[PathN] = FArg(S, "roll", 0);
	PathN++;
}

// Catmull-Rom point between B and C (A, D neighbours), U in 0..1
function vector CR(vector A, vector B, vector C, vector D, float U)
{
	local float U2, U3;
	U2 = U * U; U3 = U2 * U;
	return 0.5 * ((2 * B) + (C - A) * U + (2 * A - 5 * B + 4 * C - D) * U2 + (3 * B - A - 3 * C + D) * U3);
}

// Point on the fly path P1..Pn at parameter U (0..1), end tangents mirrored.
function vector FlyPoint(float U)
{
	local vector K[6];
	local int N, i;
	local float X;
	K[1] = P1; K[2] = P2; N = 2;
	if (bHasP3) { K[3] = P3; N = 3; }
	if (bHasP4) { K[4] = P4; N = 4; }
	K[0] = 2 * K[1] - K[2];
	K[N + 1] = 2 * K[N] - K[N - 1];
	X = FClamp(U, 0, 0.9999) * (N - 1);
	i = int(X);
	return CR(K[i], K[i + 1], K[i + 2], K[i + 3], X - i);
}

// Keep the camera in front of walls between Center and Desired.
function vector Unblock(vector Center, vector Desired)
{
	local vector HL, HN;
	if (Trace(HL, HN, Desired, Center, false) != None)
		return HL + HN * 18;
	return Desired;
}

// follow mode: horizontal "behind" direction rotated by Off degrees
function vector FollowBack(float Off)
{
	local float A;
	A = Off * 0.0174533;
	return Normal(vect(1,0,0) * (FollowDir.X * Cos(A) - FollowDir.Y * Sin(A)) + vect(0,1,0) * (FollowDir.X * Sin(A) + FollowDir.Y * Cos(A)));
}

// free fraction (0..1) of the camera line from the player to the follow spot at offset Off
function float FollowFree(vector Center, float Off)
{
	local vector HL, HN, C, Wnt;
	C = Center + vect(0,0,30);
	Wnt = Center - FollowBack(Off) * Dist + vect(0,0,1) * H;
	if (Trace(HL, HN, Wnt, C, false) == None)
		return 1;
	return VSize(HL - C) / FMax(VSize(Wnt - C), 1);
}

function float BestFollowOff(vector Center)
{
	local float Best, BestF, F, O;
	local int i;
	Best = 0; BestF = -1;
	for (i = 0; i < 7; i++)
	{
		O = 30 * ((i + 1) / 2);
		if (i % 2 == 1) O = -O;
		F = FollowFree(Center, O) - Abs(O) / 900;   // slight preference for straight behind
		if (F > BestF) { BestF = F; Best = O; }
	}
	return Best;
}

// Like Unblock, but also traces two parallel lines WideW uu to either side, so pillars next to the sight line
// (that would fill half the frame) pull the camera in as well. Side lines that start inside a wall are ignored.
function vector UnblockWide(vector Center, vector Desired)
{
	local vector HL, HN, D, S, C;
	local float F, Best;
	local int i;
	if (WideW <= 0)
		return Unblock(Center, Desired);
	D = Desired - Center;
	if (VSize(D) < 1)
		return Desired;
	S = Normal(D cross vect(0,0,1)) * WideW;
	Best = 1;
	for (i = -1; i <= 1; i++)
	{
		C = Center + S * i;
		if (i != 0 && Trace(HL, HN, C, Center, false) != None)
			continue;
		if (Trace(HL, HN, Desired + S * i, C, false) != None)
		{
			F = VSize(HL - C) / VSize(D);
			if (F < Best) Best = F;
		}
	}
	if (Best >= 1)
		return Desired;
	return Center + D * FMax(Best - 18 / VSize(D), 0.05);
}

event Tick(float DeltaTime)
{
	if (bSlave)
		return;   // driven by DDTake
	if (Compute(DeltaTime))
	{
		ApplyView(CamLoc, LookLoc, CurFovOut, CurRollOut);
		if (bStep && bActive && Mode == "PATH")
		{
			// this tick's view is drawn after Tick: "shot" saves exactly this frame, then the next frame's time
			if (StepWait > 0)
				StepWait--;
			else
			{
				Con.Viewport.Actor.ConsoleCommand("shot");
				StepCount++;
				StepT += StepDT;
				if (StepT > StepEnd + StepDT * 0.5)
				{
					bStep = false;
					Con.DDLog("PATH", "render done|frames=" $ StepCount);
				}
			}
		}
	}
}

// Put the free-cam view at Loc looking at Look.
function ApplyView(vector Loc, vector Look, float F, int RollU)
{
	local PlayerPawn S;
	S = Con.Viewport.Actor;
	S.ViewTarget = None;
	DemoPlaybackSpec(S).bLockOn = false;
	S.bBehindView = false;
	S.SetCollision(false, false, false);
	S.bCollideWorld = false;
	S.Velocity = vect(0,0,0);
	S.Acceleration = vect(0,0,0);
	S.SetLocation(Loc - vect(0,0,1) * S.EyeHeight);
	S.ViewRotation = rotator(Look - Loc);
	S.ViewRotation.Roll = RollU;
	S.DesiredFOV = F;
	S.FOVAngle = F;
}

// Advance the camera one tick; results in CamLoc, LookLoc, CurFovOut, CurRollOut. False = nothing to show.
function bool Compute(float DeltaTime)
{
	local PlayerPawn S;
	local Pawn P, L;
	local vector Center, Want, LookWant, Dir;
	local float Ang, dt, k, CurFov, TD;
	local Projectile PR;
	local float BestD;
	local vector AX, AY, AZ;
	local float BU, BFov, BR;
	local float KX, KU;
	local int K1, K0, K2;

	if (!bActive || Con == None || Con.Viewport == None)
		return false;
	S = Con.Viewport.Actor;
	if (DemoPlaybackSpec(S) == None || DemoPlaybackSpec(S).bSeeking)
		return false;
	dt = DeltaTime;
	if (bRealTime && Level.TimeDilation > 0)
		dt = DeltaTime / Level.TimeDilation;
	// deterministic camera time from demo time (pause/pre-roll proof)
	TD = Con.Watcher.DemoTime() - StartDemoT;
	if (bRealTime && Con.Watcher.RampN > 0)
		TD = Con.Watcher.WallBetween(StartDemoT, Con.Watcher.DemoTime());   // wall time under a speed ramp
	else if (bRealTime && DemoPlaybackSpec(S).Driver != None && DemoPlaybackSpec(S).Driver.mySpeed > 0)
		TD = TD / DemoPlaybackSpec(S).Driver.mySpeed;
	if (TD < 0)
		TD = 0;
	// In bullet time demo time only advances in steps (every ~0.2 s of wall time at 0.02x), which made the
	// camera pulse. Run on real time between steps, held within [TD, TD + 0.3] so it cannot drift or run on in a pause.
	if (bStep)
		T = StepT;                     // frame-stepped render: exact time per frame
	else if (bRealTime && TD > 0 && bInit)
		T = FClamp(T + dt, TD, TD + 0.3);
	else
		T = TD;

	P = FindPawn(Tgt);
	L = FindPawn(LookId);
	if (L == None) L = P;

	// --- desired camera position and look-at point ---
	if (Mode == "ORBIT")
	{
		if (P != None) Center = P.Location;
		else if (Tgt >= 0) return bInit;   // target dead: hold (P1 would be the map origin)
		else Center = P1;
		Ang = (A0 + W * T) * 0.0174533;
		Want = Center + vect(1,0,0) * Cos(Ang) * R + vect(0,1,0) * Sin(Ang) * R + vect(0,0,1) * H;
		Want = UnblockWide(Center + vect(0,0,30), Want);
		LookWant = Center;
	}
	else if (Mode == "DOLLY")
	{
		Want = P1 + (P2 - P1) * Ease(T / FMax(Dur, 0.01));
		if (bHasAt) LookWant = At; else if (L != None) LookWant = L.Location; else LookWant = P2;
		if (bHasAt || L != None) Want = Unblock(LookWant + vect(0,0,40), Want);   // crane path may cross walls
	}
	else if (Mode == "FLY")
	{
		if (!bHasP2) return bInit;
		Want = FlyPoint(Ease(T / FMax(Dur, 0.01)));
		if (bHasAt) Want = Unblock(At + vect(0,0,30), Want);   // planned points may be behind a wall
		if (bHasAt) LookWant = At;
		else if (L != None) LookWant = L.Location;
		else LookWant = Want + Normal(FlyPoint(Ease(T / FMax(Dur, 0.01) + 0.02)) - Want) * 300;
	}
	else if (Mode == "DIVE")
	{
		if (!bHasAt) return bInit;
		Dir = At - P1;
		k = FMax(VSize(Dir) - 16, 0) / FMax(VSize(Dir), 1);
		Want = P1 + Dir * k * (FClamp(T / FMax(Dur, 0.01), 0, 1) ** 2.5);
		Want = Unblock(At, Want);
		LookWant = At;
	}
	else if (Mode == "PATH")
	{
		// dense keys from tools\mapgen\cam_path.py, one every PathDT s: uniform Catmull-Rom through them. No Unblock:
		// the path is checked offline on every frame (cam_check.py), a pull-in here would make the camera jump.
		if (PathN < 2) return bInit;
		KX = FClamp(T / PathDT, 0, PathN - 1.001);
		K1 = int(KX); KU = KX - K1;
		K0 = Max(K1 - 1, 0); K2 = Min(K1 + 2, PathN - 1);
		Want = CR(PathP[K0], PathP[K1], PathP[K1 + 1], PathP[K2], KU);
		LookWant = CR(PathA[K0], PathA[K1], PathA[K1 + 1], PathA[K2], KU);
		PathFov = PathF[K1] + (PathF[K1 + 1] - PathF[K1]) * KU;
		PathRoll = PathR[K1] + (PathR[K1 + 1] - PathR[K1]) * KU;
	}
	else if (Mode == "STATIC")
	{
		Want = P1;
		if (bHasAt) Want = Unblock(At + vect(0,0,40), P1);   // planned spot may be inside a wall
		if (bHasAt) LookWant = At; else if (L != None) LookWant = L.Location; else LookWant = CamLoc + vector(S.ViewRotation) * 100;
	}
	else if (Mode == "CHASE")
	{
		if (P == None) return bInit;   // target dead: hold the last framing
		Dir = vector(P.Rotation); Dir.Z = 0; Dir = Normal(Dir);
		Want = P.Location - Dir * Dist + vect(0,0,1) * H;
		Want = Unblock(P.Location + vect(0,0,30), Want);
		LookWant = P.Location + Dir * 200;
	}
	else if (Mode == "FOLLOW")
	{
		// like CHASE, but behind the direction of travel (smoothed), not the view yaw (players spin while aiming)
		if (P == None) return bInit;
		if (bInit && VSize(P.Location - LastTgtLoc) > 400)
		{
			bInit = false;                // respawn / teleport: snap instead of dragging through walls
			FollowDir = vect(0,0,0); FollowOff = 0; FollowOffWant = 0;
		}
		LastTgtLoc = P.Location;
		Dir = P.Velocity; Dir.Z = 0;
		if (VSize(Dir) > 150)
		{
			if (FollowDir == vect(0,0,0)) FollowDir = Normal(Dir);
			else FollowDir = Normal(FollowDir + (Normal(Dir) - FollowDir) * FMin(1, dt * 2.5));
		}
		if (FollowDir == vect(0,0,0)) { FollowDir = vector(P.Rotation); FollowDir.Z = 0; FollowDir = Normal(FollowDir); }
		// swing around the player (up to +-90 deg) when the spot behind is walled in (tight rooms)
		if (FollowFree(P.Location, FollowOffWant) < 0.75 || (FollowOffWant != 0 && FollowFree(P.Location, 0) > 0.95))
			FollowOffWant = BestFollowOff(P.Location);
		FollowOff += (FollowOffWant - FollowOff) * FMin(1, dt * 2.5);
		Dir = FollowBack(FollowOff);
		Want = P.Location - Dir * Dist + vect(0,0,1) * H + (Dir cross vect(0,0,1)) * Side;
		Want = UnblockWide(P.Location + vect(0,0,30), Want);
		if (L != None && L != P) LookWant = (P.Location + L.Location) * 0.5;
		else LookWant = P.Location + FollowDir * Lead;
	}
	else if (Mode == "BALL")
	{
		if (Ball == None && Con.Watcher.DemoTime() >= StartDemoT)
		{
			BestD = 1000000;
			foreach AllActors(class'Projectile', PR)
				if (PR.Instigator != None && PR.Instigator.PlayerReplicationInfo != None
					&& PR.Instigator.PlayerReplicationInfo.PlayerID == BallBy && !PR.IsA('UTChunk'))
				{
					if (!bHasBP)
						Ball = PR;
					else if (VSize(PR.Location - BP) < BestD)
					{
						BestD = VSize(PR.Location - BP);
						Ball = PR;
					}
				}
			if (bHasBP && BestD > 450)
				Ball = None;   // the wanted ball is not out yet: keep looking (never ride an older ball)
		}
		if (Ball != None && !Ball.bDeleteMe)
		{
			BallLastLoc = Ball.Location;
			if (VSize(Ball.Velocity) > 10) BallLastDir = Normal(Ball.Velocity);
			Want = BallLastLoc - BallLastDir * Dist + vect(0,0,1) * H;
			Want = Unblock(BallLastLoc, Want);
			LookWant = BallLastLoc + BallLastDir * 300;
		}
		else if (BallLastDir != vect(0,0,0))
		{
			Want = CamLoc;                 // hold; look at the explosion point
			LookWant = BallLastLoc;
		}
		else if (P != None)
		{
			Want = P.Location - vector(P.Rotation) * Dist + vect(0,0,1) * H;   // wait behind shooter
			Want = Unblock(P.Location + vect(0,0,30), Want);
			LookWant = P.Location + vector(P.Rotation) * 300;
		}
		else return bInit;
	}
	else if (Mode == "BULLET")
	{
		// rig fixed to the bullet-time bullet (DDBullet): dist behind it (negative = ahead), r away from the flight
		// axis at angle a0 (+ w deg/s; 0 = right, 90 = above), looking at the point `lead` uu ahead of the bullet
		if (Con.Watcher.Bullet == None || !Con.Watcher.Bullet.bArmed) return bInit;
		Dir = Con.Watcher.Bullet.Dir;
		GetAxes(rotator(Dir), AX, AY, AZ);
		BU = FClamp(Con.Watcher.Bullet.T / Con.Watcher.Bullet.Dur, 0, 1);
		Ang = (BKey(2, BU) + W * T) * 0.0174533;
		if (Con.Watcher.Bullet.bHit)
			Center = Con.Watcher.Bullet.P1;       // after the impact the rig stays at the head
		else
			Center = Con.Watcher.Bullet.Location;
		BR = BKey(1, BU);
		if (Con.Watcher.Bullet.bHit && Pull != 0)
			BR += Pull * (1 - Exp(-FMax(Con.Watcher.Bullet.T - Con.Watcher.Bullet.Dur, 0) * 1.6));   // back off from the gore
		Want = Center - AX * BKey(0, BU) + (AY * Cos(Ang) + AZ * Sin(Ang)) * BR + vect(0,0,1) * BKey(4, BU);
		Want = Unblock(Center, Want);
		LookWant = Center + AX * BKey(3, BU);
		LookWant.Z += LookZ2 * Ease((BU - 0.7) / 0.3);   // frame head AND chest at the arrival (the body hangs below the bullet line)
		BFov = BKey(5, BU);
	}
	else
		return false;
	if (bLookB && Mode != "BULLET" && Con.Watcher.Bullet != None && Con.Watcher.Bullet.bArmed)
		LookWant = Con.Watcher.Bullet.Location;
	LookWant.Z += ZOff;

	// --- smoothing ---
	if (!bInit)
	{
		CamLoc = Want; LookLoc = LookWant; bInit = true;
	}
	else
	{
		k = 1 - Lag ** (dt * 60);     // frame-rate independent exponential smoothing
		CamLoc += (Want - CamLoc) * k;
		LookLoc += (LookWant - LookLoc) * FMin(1, k * 1.6);
	}

	// --- outputs (applied by Tick or blended by DDTake) ---
	CurRollOut = 0;
	if (RollW != 0 && (Mode == "FLY" || Mode == "DIVE"))
		CurRollOut = int(RollW * T * 182.044);
	if (Mode == "PATH")
		CurRollOut = int(PathRoll * 182.044);
	if (Fov2 != Fov && Dur > 0)
		CurFov = Fov + (Fov2 - Fov) * Ease(T / Dur);
	else
		CurFov = Fov;
	if (Mode == "BULLET")
		CurFov = BFov;
	if (Mode == "PATH")
		CurFov = PathFov;
	CurFovOut = CurFov;
	return true;
}

defaultproperties
{
	RemoteRole=ROLE_None
	bAlwaysTick=True
}
