import { Component, Suspense, useEffect, useRef, useState, type ReactNode } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls, useGLTF } from "@react-three/drei";
import type { Character } from "../types/character";
import { RACES, CLASSES, CLASS_COLORS } from "../utils/constants";
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const RACE_MODEL_NAMES: Record<number, string> = {
  1: "human", 2: "orc", 3: "dwarf", 4: "nightelf", 5: "undead",
  6: "tauren", 7: "gnome", 8: "troll", 10: "bloodelf", 11: "draenei",
};

interface AttachmentItem {
  displayId: number;
  attachPoint: string;
  side?: string;
  hasModel: boolean;
}

interface AttachmentPoint {
  position: number[];
  rotation: number[];
}

interface AttachmentsResponse {
  attachments: Record<string, AttachmentPoint>;
  items: Record<string, AttachmentItem>;
  race: number;
  gender: number;
}

function CharacterModel({
  race,
  gender,
  characterName,
}: {
  race: number;
  gender: number;
  characterName: string;
}) {
  const raceName = RACE_MODEL_NAMES[race] ?? "human";
  const genderStr = gender === 0 ? "male" : "female";
  const path = `/models/characters/${raceName}_${genderStr}.glb`;

  const { scene } = useGLTF(path);
  const groupRef = useRef<THREE.Group>(null!);
  const { camera } = useThree();

  useEffect(() => {
    const group = groupRef.current;
    if (!group) return;

    // Track loaded attachment models for cleanup
    const attachmentModels: THREE.Object3D[] = [];

    // Clear previous children
    while (group.children.length) group.remove(group.children[0]);

    // Deep clone scene
    const clone = scene.clone(true);

    // Collect source meshes for material copying
    const srcMeshes: THREE.Mesh[] = [];
    scene.traverse((c) => {
      if ((c as THREE.Mesh).isMesh) srcMeshes.push(c as THREE.Mesh);
    });

    let meshIdx = 0;
    clone.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        const srcMat = srcMeshes[meshIdx]?.material as THREE.MeshStandardMaterial;
        if (srcMat) {
          const newMat = srcMat.clone();
          if (srcMat.map) {
            newMat.map = srcMat.map.clone();
            newMat.map.needsUpdate = true;
          }
          newMat.needsUpdate = true;
          mesh.material = newMat;
        }
        meshIdx++;
      }
    });

    // Scale and center
    const box = new THREE.Box3().setFromObject(clone);
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    const charScale = 2.0 / maxDim;
    clone.scale.setScalar(charScale);

    const scaledBox = new THREE.Box3().setFromObject(clone);
    const scaledCenter = scaledBox.getCenter(new THREE.Vector3());
    const scaledSize = scaledBox.getSize(new THREE.Vector3());

    clone.position.sub(scaledCenter);
    clone.position.y += scaledSize.y / 2;
    clone.rotation.y = Math.PI;

    group.add(clone);

    camera.position.set(0, 1, 3.5);
    camera.lookAt(0, 0.8, 0);

    // Parse geoset node names: "geoset_{id}_{textype}" e.g. "geoset_0_skin", "geoset_101_hair"
    const parseGeosetNode = (name: string) => {
      const match = name.match(/^geoset_(\d+)_(\w+)$/);
      if (match) return { id: parseInt(match[1], 10), texType: match[2] };
      // Fallback for old naming: "geoset_{id}"
      const old = name.match(/^geoset_(\d+)$/);
      if (old) return { id: parseInt(old[1], 10), texType: "skin" };
      return null;
    };

    // Fetch active geosets from API and apply visibility
    const geosetsUrl = `/api/model-geosets/${encodeURIComponent(characterName)}`;
    fetch(geosetsUrl)
      .then((res) => res.json())
      .then((data: { geosets: number[] }) => {
        const activeSet = new Set(data.geosets);

        // Show/hide submesh nodes based on active geosets
        clone.traverse((child) => {
          const parsed = parseGeosetNode(child.name);
          if (parsed) {
            child.visible = activeSet.has(parsed.id);
          }
        });

        // After filtering geosets, recalculate bounding box for centering
        const filteredBox = new THREE.Box3().setFromObject(clone);
        const filteredCenter = filteredBox.getCenter(new THREE.Vector3());
        const filteredSize = filteredBox.getSize(new THREE.Vector3());
        clone.position.sub(filteredCenter);
        clone.position.y += filteredSize.y / 2;
      })
      .catch(() => {
        console.log("Geoset data not available, showing all meshes");
      });

    // Helper to apply a texture to meshes matching a given texture type
    const applyTextureToType = (texture: THREE.Texture, ...texTypes: string[]) => {
      clone.traverse((child) => {
        if ((child as THREE.Mesh).isMesh) {
          const mesh = child as THREE.Mesh;
          const parsed = parseGeosetNode(mesh.name);
          if (parsed && texTypes.includes(parsed.texType)) {
            const mat = mesh.material as THREE.MeshStandardMaterial;
            mat.map = texture;
            mat.needsUpdate = true;
          }
        }
      });
    };

    const texLoader = new THREE.TextureLoader();
    const setupTexture = (tex: THREE.Texture) => {
      tex.flipY = false; // GLB textures don't flip Y
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.needsUpdate = true;
    };

    // Load composited gear texture and apply to SKIN meshes only
    const textureUrl = `/api/model-texture/${encodeURIComponent(characterName)}`;
    texLoader.load(
      textureUrl,
      (gearTexture) => {
        setupTexture(gearTexture);
        applyTextureToType(gearTexture, "skin");
      },
      undefined,
      () => console.log("Gear texture not available, using base skin")
    );

    // Load hair model texture and apply to HAIR meshes
    const hairUrl = `/api/model-hair-texture/${encodeURIComponent(characterName)}`;
    texLoader.load(
      hairUrl,
      (hairTexture) => {
        setupTexture(hairTexture);
        applyTextureToType(hairTexture, "hair");
      },
      undefined,
      () => console.log("Hair texture not available")
    );

    // Load extra skin texture (tauren fur, etc.) and apply to TYPE8 meshes
    const extraSkinUrl = `/api/model-extra-skin-texture/${encodeURIComponent(characterName)}`;
    texLoader.load(
      extraSkinUrl,
      (extraSkinTexture) => {
        setupTexture(extraSkinTexture);
        applyTextureToType(extraSkinTexture, "skin_extra");
      },
      undefined,
      () => {} // Silently ignore - most races don't have type8
    );

    // Load cape/cloak texture and apply to CAPE meshes (type 2)
    const capeUrl = `/api/model-cape-texture/${encodeURIComponent(characterName)}`;
    texLoader.load(
      capeUrl,
      (capeTexture) => {
        setupTexture(capeTexture);
        applyTextureToType(capeTexture, "cape");
      },
      undefined,
      () => {} // Silently ignore - not all characters have capes
    );

    // ── Attachment Items (weapons, shields, shoulders, helms) ──
    // Fetch attachment data and load 3D item models
    const attachUrl = `/api/character-attachments/${encodeURIComponent(characterName)}`;
    fetch(attachUrl)
      .then((res) => res.json())
      .then((data: AttachmentsResponse) => {
        const { attachments, items } = data;
        const gltfLoader = new GLTFLoader();

        for (const [key, item] of Object.entries(items)) {
          if (!item.hasModel || !item.displayId) continue;

          const attachData = attachments[item.attachPoint];
          if (!attachData) continue;

          // Determine which side model to load
          const side = item.side ?? (key === "offHand" ? "left" : key.includes("Left") ? "left" : "right");
          // Helms need race/gender for race-specific models (e.g., _NiM suffix)
          const raceParam = key === "helm" ? `&race=${data.race}&gender=${data.gender}` : "";
          const modelUrl = `/api/item-model/${item.displayId}?side=${side}${raceParam}`;

          gltfLoader.load(
            modelUrl,
            (gltf) => {
              const itemModel = gltf.scene;

              // Attachment position is in glTF model space (same as character GLB vertices).
              const pos = new THREE.Vector3(
                attachData.position[0],
                attachData.position[1],
                attachData.position[2],
              );

              // Create a pivot group at the attachment point
              const pivot = new THREE.Group();
              pivot.position.copy(pos);
              pivot.name = `attach_${key}`;

              // Apply bone rotation from Stand animation frame 0.
              // This orients items correctly based on the bone's world transform.
              const rot = attachData.rotation;
              if (rot) {
                pivot.quaternion.set(rot[0], rot[1], rot[2], rot[3]);
              }

              pivot.add(itemModel);

              clone.add(pivot);
              attachmentModels.push(pivot);
            },
            undefined,
            () => {} // Silently ignore failed item model loads
          );
        }
      })
      .catch(() => {}); // Silently ignore if attachments not available

    return () => {
      // Cleanup attachment models
      for (const model of attachmentModels) {
        model.traverse((child) => {
          if ((child as THREE.Mesh).isMesh) {
            const mesh = child as THREE.Mesh;
            const mat = mesh.material as THREE.MeshStandardMaterial;
            mat.map?.dispose();
            mat.dispose();
            mesh.geometry.dispose();
          }
        });
      }
      clone.traverse((child) => {
        if ((child as THREE.Mesh).isMesh) {
          const mesh = child as THREE.Mesh;
          const mat = mesh.material as THREE.MeshStandardMaterial;
          mat.map?.dispose();
          mat.dispose();
          mesh.geometry.dispose();
        }
      });
    };
  }, [scene, race, gender, characterName, camera]);

  return <group ref={groupRef} />;
}

function LoadingIndicator() {
  return (
    <mesh position={[0, 1, 0]}>
      <sphereGeometry args={[0.1, 16, 16]} />
      <meshBasicMaterial color="#ffd700" wireframe />
    </mesh>
  );
}

function FallbackDisplay({ character }: { character: Character }) {
  const classColor = CLASS_COLORS[character.class] ?? "#ffffff";
  const raceName = RACES[character.race] ?? "Unknown";
  const className = CLASSES[character.class] ?? "Unknown";

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        padding: 20,
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: 80, marginBottom: 20, color: classColor }}>
        {"\u2694\uFE0F"}
      </div>
      <div style={{ fontSize: 24, color: classColor, fontWeight: "bold" }}>
        {character.name}
      </div>
      <div style={{ fontSize: 18, color: "#ffd700", marginTop: 10 }}>
        Level {character.level} {raceName} {className}
      </div>
      <div style={{ fontSize: 14, color: "#999", marginTop: 20 }}>
        3D model not available
      </div>
    </div>
  );
}

function Scene({ character }: { character: Character }) {
  return (
    <Canvas camera={{ position: [0, 1, 3.5], fov: 40 }} gl={{ antialias: true }}>
      <ambientLight intensity={0.6} />
      <directionalLight position={[3, 4, 3]} intensity={1.2} />
      <directionalLight position={[-2, 2, 1]} intensity={0.5} />
      <directionalLight position={[0, 2, -3]} intensity={0.3} />

      <Suspense fallback={<LoadingIndicator />}>
        <CharacterModel
          race={character.race}
          gender={character.gender}
          characterName={character.name}
        />
      </Suspense>

      <OrbitControls
        target={[0, 0.8, 0]}
        enablePan={false}
        minDistance={1.5}
        maxDistance={8}
        maxPolarAngle={Math.PI * 0.85}
      />
    </Canvas>
  );
}

interface EBProps {
  children: ReactNode;
  onError: () => void;
}
interface EBState {
  hasError: boolean;
}

class ModelErrorBoundary extends Component<EBProps, EBState> {
  state: EBState = { hasError: false };

  static getDerivedStateFromError(): EBState {
    return { hasError: true };
  }

  componentDidCatch() {
    this.props.onError();
  }

  render() {
    if (this.state.hasError) return null;
    return this.props.children;
  }
}

interface Props {
  character: Character;
}

export default function ModelViewer({ character }: Props) {
  const [has3D, setHas3D] = useState(true);

  return (
    <div className="model-viewer">
      {has3D ? (
        <ModelErrorBoundary onError={() => setHas3D(false)}>
          <Scene character={character} />
        </ModelErrorBoundary>
      ) : (
        <FallbackDisplay character={character} />
      )}
    </div>
  );
}
