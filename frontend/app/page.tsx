
"use client";

import {
  LiveKitRoom,
  RoomAudioRenderer,
  StartAudio,
  BarVisualizer,
  VideoConference,
  ControlBar,

  useVoiceAssistant,
} from "@livekit/components-react";

import { useEffect, useState } from "react";
import "@livekit/components-styles";

export default function Home() {
  const [token, setToken] = useState<string>("");
  const [url, setUrl] = useState<string>("");

  useEffect(() => {
    (async () => {
      try {
        const resp = await fetch("http://localhost:8000/token?participant_name=Candidate1");
        const data = await resp.json();
        setToken(data.token);
        setUrl(process.env.NEXT_PUBLIC_LIVEKIT_URL || "");
      } catch (e) {
        console.error(e);
      }
    })();
  }, []);

  if (token === "") {
    return <div className="flex items-center justify-center h-screen">Loading...</div>;
  }

  return (
    <LiveKitRoom
      video={true}
      audio={true}
      token={token}
      serverUrl={url}
      data-lk-theme="default"
      className="flex flex-col items-center justify-center h-screen bg-gray-950 text-white"
    >
      <div className="w-full h-full">
        <h1 className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-600 text-center py-4">
          AI Interviewer
        </h1>
        <VideoConference />
        <RoomAudioRenderer />
        <StartAudio label="Click to allow audio playback" />
      </div>
    </LiveKitRoom>
  );
}

function SimpleVoiceVisualizer() {
  const { state, audioTrack } = useVoiceAssistant();
  return (
    <div className="relative w-full h-full flex items-center justify-center">
      <BarVisualizer state={state} barCount={7} trackRef={audioTrack} className="h-20 w-64" style={{ height: '100px' }} />
    </div>
  );
}
