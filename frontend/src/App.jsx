import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import TextEval from './pages/TextEval'
import ImageEval from './pages/ImageEval'
import VideoEval from './pages/VideoEval'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route element={<Layout />}>
        <Route path="text" element={<TextEval />} />
        <Route path="image" element={<ImageEval />} />
        <Route path="video" element={<VideoEval />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App