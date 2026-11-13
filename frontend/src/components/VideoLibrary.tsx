import type { Video } from '../types';
import { formatTime } from '../services/playback';
export function VideoLibrary({videos,selected,onSelect,refresh,loading}:{videos:Video[];selected:string|undefined;onSelect:(video:Video)=>void;refresh:()=>void;loading:boolean}) {
 return <section className="video-library" aria-label="Video library"><header><h2>Your videos</h2><button className="text-action" aria-label="Refresh library" disabled={loading} onClick={refresh}>↻</button></header><div className="recent-list" aria-label="Recent videos">
 {loading && <p>Loading your library…</p>}{!loading && !videos.length && <p>Your imported videos will appear here.</p>}
 {videos.map(video=><button key={video.id} className={`recent-video ${selected===video.id?'selected':''}`} aria-pressed={selected===video.id} onClick={()=>onSelect(video)}><span className="library-thumbnail"><img src={`/api/videos/${video.id}/preview?timestamp=${Math.min(1,Math.max(0,video.duration-.1))}`} alt="" loading="lazy" onError={e=>{e.currentTarget.style.display='none';}}/><span>{formatTime(video.duration)}</span></span><span className="recent-info"><strong>{video.title??video.original_name}</strong><small>{video.imported_from==='douyin'?'Douyin':'Local video'}</small></span></button>)}
 </div></section>;
}
