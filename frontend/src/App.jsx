import { useState } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import SplashScreen from './components/splash/SplashScreen'
import AppShell from './components/layout/AppShell'
import PageTransition from './components/layout/PageTransition'
import HomePage from './pages/HomePage'
import ProcessingPage from './pages/ProcessingPage'
import ResultPage from './pages/ResultPage'

function AnimatedRoutes() {
  const location = useLocation()

  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route
          path="/"
          element={
            <PageTransition>
              <HomePage />
            </PageTransition>
          }
        />
        <Route
          path="/processing"
          element={
            <PageTransition>
              <ProcessingPage />
            </PageTransition>
          }
        />
        <Route
          path="/result"
          element={
            <PageTransition>
              <ResultPage />
            </PageTransition>
          }
        />
      </Routes>
    </AnimatePresence>
  )
}

export default function App() {
  const [splashDone, setSplashDone] = useState(false)

  if (!splashDone) {
    return <SplashScreen onComplete={() => setSplashDone(true)} />
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
    >
      <AppShell>
        <AnimatedRoutes />
      </AppShell>
    </motion.div>
  )
}
