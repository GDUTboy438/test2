import type {
  DirectoryNode,
  LibraryInfo,
  ScanProgressInfo,
  SceneId,
  VideoItem,
  ViewMode,
} from "../types/domain";

type SceneFixture = {
  library: LibraryInfo;
  directories: DirectoryNode[];
  items: VideoItem[];
  selectedDirectoryId: string;
  searchInput: string;
  viewMode: ViewMode;
  selectedVideoId: string | null;
  scan: ScanProgressInfo;
};

const library: LibraryInfo = {
  name: "VisionVault",
  root: "E:/Media/VisionVault",
};

const directories: DirectoryNode[] = [
  {
    id: "Movies",
    name: "Movies",
    path: "/Movies",
    hasChildren: true,
    children: [
      {
        id: "Movies/2023 Trending",
        name: "2023 Trending",
        path: "/Movies/2023 Trending",
        hasChildren: false,
        children: [],
      },
      {
        id: "Movies/Sci-Fi Collection",
        name: "Sci-Fi Collection",
        path: "/Movies/Sci-Fi Collection",
        hasChildren: false,
        children: [],
      },
    ],
  },
  {
    id: "Documentary",
    name: "Documentary",
    path: "/Documentary",
    hasChildren: false,
    children: [],
  },
  {
    id: "TV Series",
    name: "TV Series",
    path: "/TV Series",
    hasChildren: false,
    children: [],
  },
  {
    id: "Personal Clips",
    name: "Personal Clips",
    path: "/Personal Clips",
    hasChildren: false,
    children: [],
  },
  {
    id: "Unsorted Assets",
    name: "Unsorted Assets",
    path: "/Unsorted Assets",
    hasChildren: false,
    children: [],
  },
];

const scan: ScanProgressInfo = {
  title: "Scanning: /Movies/2023/Oppenheimer...",
  percentText: "68%",
  percentValue: 68,
};

const sampleVideos: VideoItem[] = [
  {
    id: "Movies/Interstellar.2014.2160p.mkv",
    name: "Interstellar.2014.2160p",
    path: "/MOVIES/SCI-FI",
    filePath: "/Movies/Interstellar.2014.2160p.mkv",
    duration: "02:49:03",
    resolution: "4K",
    size: "42.5 GB",
    modified: "2024-03-15",
    status: "Indexed",
    tags: ["Sci-Fi", "4K"],
    detail: "Format: MKV | Resolution: 4K",
    thumbUrl: null,
  },
  {
    id: "Movies/Oppenheimer.2023.HDR.mkv",
    name: "Oppenheimer.2023.HDR",
    path: "/MOVIES/2023",
    filePath: "/Movies/Oppenheimer.2023.HDR.mkv",
    duration: "03:00:21",
    resolution: "4K",
    size: "18.2 GB",
    modified: "2024-03-20",
    status: "Scanning...",
    tags: ["Drama", "4K"],
    detail: "Format: MKV | Resolution: 4K",
    thumbUrl: null,
  },
  {
    id: "Movies/Planet.Earth.S03E01.1080p.mkv",
    name: "Planet.Earth.S03E01.1080p",
    path: "/MOVIES/DOCUMENTARY",
    filePath: "/Movies/Planet.Earth.S03E01.1080p.mkv",
    duration: "00:58:12",
    resolution: "1080P",
    size: "4.8 GB",
    modified: "2024-01-10",
    status: "Indexed",
    tags: ["Documentary"],
    detail: "Format: MKV | Resolution: 1080P",
    thumbUrl: null,
  },
  {
    id: "Movies/Clip_001.mp4",
    name: "Clip_001",
    path: "/RAW/CLIPS",
    filePath: "/Movies/Clip_001.mp4",
    duration: "00:15:30",
    resolution: "1080P",
    size: "2.1 GB",
    modified: "2024-05-02",
    status: "Queued",
    tags: ["Raw"],
    detail: "Format: MP4 | Resolution: 1080P",
    thumbUrl: null,
  },
  {
    id: "Movies/Family.Gathering.2024.mp4",
    name: "Family.Gathering.2024",
    path: "/PERSONAL",
    filePath: "/Movies/Family.Gathering.2024.mp4",
    duration: "00:45:12",
    resolution: "1080P",
    size: "3.4 GB",
    modified: "2024-05-18",
    status: "Indexed",
    tags: ["Family"],
    detail: "Format: MP4 | Resolution: 1080P",
    thumbUrl: null,
  },
  {
    id: "Movies/Blade.Runner.2049.mkv",
    name: "Blade.Runner.2049",
    path: "/MOVIES/SCI-FI",
    filePath: "/Movies/Blade.Runner.2049.mkv",
    duration: "02:44:00",
    resolution: "4K",
    size: "21.3 GB",
    modified: "2024-02-12",
    status: "Indexed",
    tags: ["Sci-Fi", "Neo-noir"],
    detail: "Format: MKV | Resolution: 4K",
    thumbUrl: null,
  },
  {
    id: "Movies/Dune.Part.Two.2024.mkv",
    name: "Dune.Part.Two.2024",
    path: "/MOVIES/2024",
    filePath: "/Movies/Dune.Part.Two.2024.mkv",
    duration: "02:46:30",
    resolution: "4K",
    size: "29.9 GB",
    modified: "2024-06-02",
    status: "Scanning...",
    tags: ["Sci-Fi", "Epic"],
    detail: "Format: MKV | Resolution: 4K",
    thumbUrl: null,
  },
  {
    id: "Movies/Nature.Run.2019.mp4",
    name: "Nature.Run.2019",
    path: "/MOVIES/DOCUMENTARY",
    filePath: "/Movies/Nature.Run.2019.mp4",
    duration: "01:09:05",
    resolution: "1080P",
    size: "5.4 GB",
    modified: "2023-12-01",
    status: "Indexed",
    tags: ["Nature"],
    detail: "Format: MP4 | Resolution: 1080P",
    thumbUrl: null,
  },
  {
    id: "Movies/Travel.Lens.2021.mp4",
    name: "Travel.Lens.2021",
    path: "/MOVIES/TRAVEL",
    filePath: "/Movies/Travel.Lens.2021.mp4",
    duration: "00:34:10",
    resolution: "1080P",
    size: "1.7 GB",
    modified: "2023-10-03",
    status: "Indexed",
    tags: ["Travel"],
    detail: "Format: MP4 | Resolution: 1080P",
    thumbUrl: null,
  },
  {
    id: "Movies/Studio.Behind.The.Scene.mp4",
    name: "Studio.Behind.The.Scene",
    path: "/MOVIES/FEATURETTE",
    filePath: "/Movies/Studio.Behind.The.Scene.mp4",
    duration: "00:12:33",
    resolution: "720P",
    size: "0.8 GB",
    modified: "2024-01-04",
    status: "Indexed",
    tags: ["Featurette"],
    detail: "Format: MP4 | Resolution: 720P",
    thumbUrl: null,
  },
];

const fixtures: Record<SceneId, SceneFixture> = {
  "5JcTk": {
    library,
    directories,
    items: sampleVideos.slice(0, 5),
    selectedDirectoryId: "Movies",
    searchInput: "",
    viewMode: "list",
    selectedVideoId: null,
    scan,
  },
  "88L9O": {
    library,
    directories,
    items: sampleVideos.slice(0, 5),
    selectedDirectoryId: "Movies",
    searchInput: "",
    viewMode: "list",
    selectedVideoId: "Movies/Oppenheimer.2023.HDR.mkv",
    scan,
  },
  JrodX: {
    library,
    directories,
    items: sampleVideos,
    selectedDirectoryId: "Movies",
    searchInput: "",
    viewMode: "grid",
    selectedVideoId: null,
    scan,
  },
  "2L8Xf": {
    library,
    directories,
    items: sampleVideos.slice(0, 8),
    selectedDirectoryId: "Movies",
    searchInput: "",
    viewMode: "grid",
    selectedVideoId: "Movies/Oppenheimer.2023.HDR.mkv",
    scan,
  },
};

export function getSceneFixture(sceneId: SceneId): SceneFixture {
  return JSON.parse(JSON.stringify(fixtures[sceneId])) as SceneFixture;
}
