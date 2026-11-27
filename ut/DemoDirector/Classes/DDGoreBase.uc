//=============================================================================
// DDGoreBase - optional gore provider for DDBullet's impact.
// DemoDirector itself must not depend on a gore mod (the package would not load without it), so DDBullet loads a
// subclass by name at runtime (gorefx=, default DDUltraGore.DDUltraGoreFX, built only when the Ultra Gore SSE mod is
// installed) and falls back to stock UT blood when none is found.
//=============================================================================
class DDGoreBase extends Info;

// One headshot burst at B.P1 along B.Dir. Return false if nothing was spawned (DDBullet then uses stock blood).
function bool Burst(DDBullet B, Pawn Victim, Pawn Killer)
{
	return false;
}

defaultproperties
{
	RemoteRole=ROLE_None
}
