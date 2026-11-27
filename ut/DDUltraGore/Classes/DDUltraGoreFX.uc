//=============================================================================
// DDUltraGoreFX - DDBullet's impact gore from the Ultra Gore SSE mod (NWUltraGoreSSEd, by Feralidragon).
// Separate package so DemoDirector.u loads without the mod; DDBullet finds this class by name (gorefx=).
//
// Ultra Gore is a server mutator: a demo only contains the gore the original server sent, so enabling the mutator
// changes nothing in playback. Its effect classes can be spawned locally though (a locally spawned actor has
// Role = Authority): this does what the mutator's setupVictimGoreFX does for a 'Decapitated' kill.
// Needs System\NWUltraGoreSSEd.u (+ .int, .ini) installed. Build: EditPackages NWUltraGoreSSEd, DDUltraGore after
// DemoDirector in DDMake.ini.
//=============================================================================
class DDUltraGoreFX extends DDGoreBase;

var NWBloodyMess_UGSSE Mut;

// One burst piece. A (splat sprite), B (spawns the meat, cords and skull pieces), C (blood fog sprite).
function GoreFX(DDBullet B, class<NWBloodExplFX_UGSSE> C, Actor Ref, Pawn K, class<NWGoreCBoard_UGSSE> Board,
	float LifeMult, bool bSound, string Ids, float SprScale)
{
	local NWBloodExplFX_UGSSE FX;
	local vector M;
	FX = Spawn(C,,, B.P1);
	if (FX == None)
		return;
	M = B.Dir * B.GoreMom;
	M.Z = FMax(M.Z, 0.4 * B.GoreMom);
	FX.InitBloodFX('Decapitated', Ref, Board, Mut, Ids, true, LifeMult, K, M);
	FX.Victim.Location = B.P1 - vect(0,0,27);   // skull fragments are placed at victim + 27 uu = the head
	if (FX.Victim.Scale <= 0)
		FX.Victim.Scale = 1;                     // 0 = nothing spawns (and can hang the mod's loop)
	// the sprites (splat, fog) are size-only for A and C; B keeps fxScale because it sizes the flying pieces
	if (!FX.bSpawnPieces)
		FX.fxScale *= SprScale;
	FX.DrawScale *= SprScale;
	if (bSound)
		FX.MakeGoreSound();
}

function bool Burst(DDBullet B, Pawn V, Pawn K)
{
	local Actor Ref;
	local class<NWGoreCBoard_UGSSE> Board;
	local int i;
	Ref = V;                                     // size reference; must not be None
	if (Ref == None) Ref = K;
	if (Ref == None) Ref = B.Con.Viewport.Actor;
	if (Mut == None)
		Mut = Spawn(class'NWBloodyMess_UGSSE');  // initialises itself from NWUltraGoreSSE.ini (one 'Game' warning)
	if (Mut == None)
	{
		B.Con.DDLog("GORE", "failed=nomutator");
		return false;
	}
	// blood=auto keeps the mod's rule (Xan/Boss models and cyborg skins bleed SILVER, Mercenaries green)
	if (B.bAutoBlood)
		Board = Mut.GetGoreBloodManagerClass(Mut.GetGoreBloodType(V));
	if (Board == None)
		Board = class'NWGoreCBoard_UGSSE';
	for (i = 0; i < B.GoreN; i++)
	{
		GoreFX(B, class'NWHeadShotExplFXA_UGSSE', Ref, K, Board, 0, false, "0,1,2", B.SplatScale);
		GoreFX(B, class'NWHeadShotExplFXB_UGSSE', Ref, K, Board, 0, i == 0, "0,1,2", B.SplatScale);
		if (i == 0 && B.FogScale > 0)
			GoreFX(B, class'NWHeadShotExplFXC_UGSSE', Ref, K, Board, 1.0, false, "0,1,2", B.FogScale);   // one fog only
	}
	for (i = 0; i < B.SkullN; i++)
		GoreFX(B, class'NWHeadShotExplFXB_UGSSE', Ref, K, Board, 0, false, "2,0", B.SplatScale * 0.6);   // more bone
	B.Con.DDLog("GORE", "ultra=" $ B.GoreN $ "|skull=" $ B.SkullN $ "|fog=" $ B.FogScale $ "|at=" $ B.P1 $ "|victim=" $ V
		$ "|board=" $ Board);
	return true;
}
