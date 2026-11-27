//=============================================================================
// DDCineHUD - cinematic HUD: crosshair (first person) + kill/center messages only.
// No status, weapons, ammo, frags, team info, faces, chat, scoreboard or mutator
// overlays. Draws small name tags for players listed in Con.TagIds during free-cam shots.
//=============================================================================
class DDCineHUD extends ChallengeCTFHUD;

var DDConsole Con;

simulated function PostRender(canvas Canvas)
{
	bHideStatus = true;
	bHideAllWeapons = true;
	bHideAmmo = true;
	bHideTeamInfo = true;
	bHideFrags = true;
	bHideFaces = true;
	bHideHUD = false;
	bHideCenterMessages = NoMessages();
	if (NoMessages())
		DropMessages();
	HUDMutator = None;
	if (PlayerPawn(Owner) != None)
		PlayerPawn(Owner).bShowScores = false;
	Super.PostRender(Canvas);
	DrawTags(Canvas);
}

// everything except crosshair + messages is switched off
simulated function DrawStatus(Canvas Canvas) {}
simulated function DrawAmmo(Canvas Canvas) {}
simulated function DrawFragCount(Canvas Canvas) {}
simulated function DrawGameSynopsis(Canvas Canvas) {}
simulated function DrawWeapons(Canvas Canvas) {}
simulated function DrawMOTD(Canvas Canvas) {}
simulated function DisplayProgressMessage(canvas Canvas) {}
simulated function bool DrawIdentifyInfo(canvas Canvas) { return false; }

// HUD mode 3: crosshair + name tags only (no kill feed, no center messages)
simulated function bool NoMessages()
{
	return Con != None && Con.HudMode == 3;
}

simulated function DropMessages()
{
	local int i;
	for (i = 0; i < ArrayCount(LocalMessages); i++)
		ClearMessage(LocalMessages[i]);
	for (i = 0; i < ArrayCount(ShortMessageQueue); i++)
		ClearMessage(ShortMessageQueue[i]);
}

simulated function Message(PlayerReplicationInfo PRI, coerce string Msg, name MsgType)
{
	if (MsgType == 'Say' || MsgType == 'TeamSay')
		return;   // no chat
	if (NoMessages())
		return;
	Super.Message(PRI, Msg, MsgType);
}

simulated function LocalizedMessage(class<LocalMessage> Message, optional int Switch, optional PlayerReplicationInfo RelatedPRI_1, optional PlayerReplicationInfo RelatedPRI_2, optional Object OptionalObject, optional string CriticalString)
{
	if (NoMessages())
		return;
	Super.LocalizedMessage(Message, Switch, RelatedPRI_1, RelatedPRI_2, OptionalObject, CriticalString);
}

// Project a world point to the screen for the current free-cam view.
simulated function bool Project(Canvas C, vector CamLoc, rotator CamRot, float Fov, vector P, out float SX, out float SY)
{
	local vector X, Y, Z, D;
	local float Depth, F;
	GetAxes(CamRot, X, Y, Z);
	D = P - CamLoc;
	Depth = D dot X;
	if (Depth < 20)
		return false;
	F = (C.ClipX * 0.5) / Tan(Fov * 0.5 * 0.0174533);
	SX = C.ClipX * 0.5 + (D dot Y) / Depth * F;
	SY = C.ClipY * 0.5 - (D dot Z) / Depth * F;
	return SX > 0 && SX < C.ClipX && SY > 0 && SY < C.ClipY;
}

simulated function DrawTags(Canvas C)
{
	local PlayerPawn S;
	local Pawn P;
	local vector CamLoc;
	local float SX, SY, XL, YL;
	local string N;
	if (Con == None || Con.TagIds == "")
		return;
	S = PlayerPawn(Owner);
	if (S == None || S.ViewTarget != None)
		return;   // tags only in free-cam (camera pose known exactly)
	CamLoc = S.Location + vect(0,0,1) * S.EyeHeight;
	C.Font = MyFonts.GetSmallFont(C.ClipX);
	C.Style = ERenderStyle.STY_Normal;
	foreach AllActors(class'Pawn', P)
	{
		if (P.PlayerReplicationInfo == None || P.IsA('Spectator') || P == S || P.Health <= 0)
			continue;
		if (InStr(Con.TagIds, " " $ P.PlayerReplicationInfo.PlayerID $ " ") < 0)
			continue;
		if (!FastTrace(P.Location, CamLoc))
			continue;
		if (!Project(C, CamLoc, S.ViewRotation, S.FOVAngle, P.Location + vect(0,0,1) * (P.CollisionHeight + 22), SX, SY))
			continue;
		N = P.PlayerReplicationInfo.PlayerName;
		C.StrLen(N, XL, YL);
		C.DrawColor.R = 0; C.DrawColor.G = 0; C.DrawColor.B = 0;
		C.SetPos(SX - XL * 0.5 + 1, SY - YL + 1);
		C.DrawText(N, false);
		C.DrawColor.R = 225; C.DrawColor.G = 205; C.DrawColor.B = 255;
		C.SetPos(SX - XL * 0.5, SY - YL);
		C.DrawText(N, false);
	}
}

defaultproperties
{
	RemoteRole=ROLE_None
}
