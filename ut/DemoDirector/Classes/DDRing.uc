//=============================================================================
// DDRing - air ripple left behind by the bullet-time bullet (DDBullet): a translucent quad perpendicular to the
// flight path that grows and fades in REAL time (it keeps expanding while the demo is almost frozen).
// Also used as the vapour-trail puff (bPuff: small sprite).
//=============================================================================
class DDRing extends Effects;

#exec MESH IMPORT MESH=DDRingM ANIVFILE=MODELS\ddring_a.3d DATAFILE=MODELS\ddring_d.3d X=0 Y=0 Z=0
#exec MESH ORIGIN MESH=DDRingM X=0 Y=0 Z=0
#exec MESH SEQUENCE MESH=DDRingM SEQ=All STARTFRAME=0 NUMFRAMES=1
#exec TEXTURE IMPORT NAME=DDRingTex FILE=TEXTURES\ddring.bmp GROUP=Skins
#exec TEXTURE IMPORT NAME=DDWakeTex FILE=TEXTURES\ddwake.bmp GROUP=Skins
#exec MESHMAP NEW MESHMAP=DDRingM MESH=DDRingM
#exec MESHMAP SCALE MESHMAP=DDRingM X=0.01 Y=0.01 Z=0.02
#exec MESHMAP SETTEXTURE MESHMAP=DDRingM NUM=1 TEXTURE=DDRingTex

var float Age, Life, S0, S1, G0;

function Setup(float NewLife, float Scale0, float Scale1, float Glow, bool bPuff)
{
	Life = FMax(NewLife, 0.05);
	S0 = Scale0; S1 = Scale1; G0 = Glow;
	Age = 0;
	if (bPuff)
	{
		DrawType = DT_Sprite;
		Texture = Texture'DDWakeTex';
	}
	DrawScale = S0;
	ScaleGlow = G0;
}

event Tick(float DeltaTime)
{
	local float dt, U;
	dt = DeltaTime;
	if (Level.TimeDilation > 0)
		dt = DeltaTime / Level.TimeDilation;
	Age += dt;
	U = Age / Life;
	if (U >= 1)
	{
		Destroy();
		return;
	}
	DrawScale = S0 + (S1 - S0) * (1 - (1 - U) * (1 - U));
	ScaleGlow = G0 * (1 - U) * (1 - U);
}

defaultproperties
{
	DrawType=DT_Mesh
	Mesh=LodMesh'DemoDirector.DDRingM'
	Style=STY_Translucent
	bUnlit=True
	RemoteRole=ROLE_None
	bAlwaysTick=True
	Physics=PHYS_None
	LifeSpan=0
	Life=1.0
	S0=0.3
	S1=2.5
	G0=1.0
	bCollideActors=False
	bCollideWorld=False
}
