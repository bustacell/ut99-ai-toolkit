//=============================================================================
// DDTake - one continuous camera ("one take") built from a timeline of DDCam rigs.
// Each rig is a DDCam (any mode) that takes over at demo time start=, crossfading from the
// previous rig over blend= demo seconds (smoothstep on position, look direction, fov, roll).
// Only the current rig (and the previous one while blending) is computed, so a rig whose
// target is dead or respawned elsewhere never pulls the view.
//
//   ddtake clear
//   ddtake add start=545.2 blend=1.5 mode=follow tgt=4 dist=260 h=90 ...   (dt0 defaults to start)
//   ddtake go          (starts applying)       ddtake off
//=============================================================================
class DDTake extends Info;

var DDConsole Con;
var DDCam Rig[48];
var float RigAt[48];
var float RigBlend[48];
var float RigWhip[48];      // whip=<deg>: the transition is a whip-pan of that total angle (hidden cut) instead of a crossfade
var int N;
var bool bActive;
var int LastK;

function Clear()
{
	local int i;
	for (i = 0; i < N; i++)
		if (Rig[i] != None)
			Rig[i].Destroy();
	N = 0;
	bActive = false;
	LastK = -1;
	Con.DDLog("TAKE", "clear");
}

function Add(string S)
{
	local DDCam C;
	local float At;
	if (N >= 48)
		return;
	C = Spawn(class'DDCam');
	if (C == None)
		return;
	C.Con = Con;
	C.bSlave = true;
	At = C.FArg(S, "start", 0);   // not "at": that is DDCam's look-at point
	if (C.Arg(S, "dt0") == "")
		S = S $ " dt0=" $ At;
	C.Configure(S);
	Rig[N] = C;
	RigAt[N] = At;
	RigBlend[N] = FMax(C.FArg(S, "blend", 0), 0);
	RigWhip[N] = C.FArg(S, "whip", 0);
	N++;
	Con.DDLog("TAKE", "add|n=" $ N $ "|at=" $ At $ "|blend=" $ RigBlend[N - 1]);
}

function Go(bool bOn)
{
	bActive = bOn && N > 0;
	LastK = -1;
	Con.DDLog("TAKE", "go=" $ bActive $ "|n=" $ N);
	if (!bActive && Con.Viewport != None && Con.Viewport.Actor != None)
	{
		Con.Viewport.Actor.DesiredFOV = Con.Viewport.Actor.DefaultFOV;
		Con.Viewport.Actor.FOVAngle = Con.Viewport.Actor.DefaultFOV;
	}
}

event Tick(float DeltaTime)
{
	local PlayerPawn S;
	local float TD, W;
	local int k, i;
	local vector Loc, D0, D1, D;
	local float F;
	local int RollU;
	local bool b0, b1;

	if (!bActive || Con == None || Con.Viewport == None || Con.Watcher == None)
		return;
	S = Con.Viewport.Actor;
	if (DemoPlaybackSpec(S) == None || DemoPlaybackSpec(S).bSeeking)
		return;
	TD = Con.Watcher.DemoTime();
	k = 0;
	for (i = 1; i < N; i++)
		if (TD >= RigAt[i])
			k = i;
	if (k != LastK)
	{
		Con.DDLog("TAKE", "rig=" $ k $ "|mode=" $ Rig[k].Mode);
		LastK = k;
	}
	// whip-pan transition: spin away from the old rig, switch at the fastest point, spin into the new one
	if (k > 0 && RigWhip[k] != 0 && RigBlend[k] > 0 && TD < RigAt[k] + RigBlend[k])
	{
		W = FClamp((TD - RigAt[k]) / RigBlend[k], 0, 1);
		b1 = Rig[k].Compute(DeltaTime);
		if (W < 0.5)
		{
			b0 = Rig[k - 1].Compute(DeltaTime);
			if (b0)
				Whip(Rig[k - 1], RigWhip[k] * Rig[k].Ease(W), W);
			else if (b1)
				Whip(Rig[k], RigWhip[k] * (Rig[k].Ease(W) - 1), W);
		}
		else if (b1)
			Whip(Rig[k], RigWhip[k] * (Rig[k].Ease(W) - 1), W);
		return;
	}
	W = 1;
	if (k > 0 && RigBlend[k] > 0)
		W = Rig[k].Ease((TD - RigAt[k]) / RigBlend[k]);
	b1 = Rig[k].Compute(DeltaTime);
	if (W < 1)
		b0 = Rig[k - 1].Compute(DeltaTime);
	if (!b1 && !b0)
		return;
	if (!b0 || W >= 1)
	{
		Rig[k].ApplyView(Rig[k].CamLoc, Rig[k].LookLoc, Rig[k].CurFovOut, Rig[k].CurRollOut);
		return;
	}
	if (!b1)
	{
		Rig[k - 1].ApplyView(Rig[k - 1].CamLoc, Rig[k - 1].LookLoc, Rig[k - 1].CurFovOut, Rig[k - 1].CurRollOut);
		return;
	}
	// crossfade: position lerp, look direction nlerp, fov / roll lerp
	Loc = Rig[k - 1].CamLoc + (Rig[k].CamLoc - Rig[k - 1].CamLoc) * W;
	D0 = Normal(Rig[k - 1].LookLoc - Rig[k - 1].CamLoc);
	D1 = Normal(Rig[k].LookLoc - Rig[k].CamLoc);
	D = D0 * (1 - W) + D1 * W;
	if (VSize(D) < 0.05)
		D = D1;   // opposite directions: avoid a degenerate look vector
	F = Rig[k - 1].CurFovOut + (Rig[k].CurFovOut - Rig[k - 1].CurFovOut) * W;
	RollU = int(Rig[k - 1].CurRollOut + (Rig[k].CurRollOut - Rig[k - 1].CurRollOut) * W);
	Rig[k].ApplyView(Loc, Loc + Normal(D) * 500, F, RollU);
}

// show rig C with its look direction turned by YawDeg around the vertical axis (+ a small fov punch)
function Whip(DDCam C, float YawDeg, float U)
{
	local vector D, R;
	local float A;
	A = YawDeg * 0.0174533;
	D = C.LookLoc - C.CamLoc;
	R = vect(1,0,0) * (D.X * Cos(A) - D.Y * Sin(A)) + vect(0,1,0) * (D.X * Sin(A) + D.Y * Cos(A)) + vect(0,0,1) * D.Z;
	C.ApplyView(C.CamLoc, C.CamLoc + R, C.CurFovOut + 12 * Sin(3.14159 * U), C.CurRollOut);
}

defaultproperties
{
	RemoteRole=ROLE_None
	bAlwaysTick=True
	LastK=-1
}
