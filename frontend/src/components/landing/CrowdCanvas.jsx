import { gsap } from 'gsap'
import { useEffect, useRef } from 'react'

const DEFAULT_SRC =
  'https://s3-us-west-2.amazonaws.com/s.cdpn.io/175711/open-peeps-sheet.png'

const UNIFORM_SCALE = 0.76
const UNIFORM_OPACITY = 0.86
const FOOT_LIFT = [0, 10]

/**
 * Animated crowd — Open Peeps / zadvorsky demo, tuned for AutoShorts landing hero.
 * Illustration: openpeeps.com (CC0)
 */
export default function CrowdCanvas({
  src = DEFAULT_SRC,
  rows = 15,
  cols = 7,
  maxCrowd = 60,
  className = '',
}) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const config = { src, rows, cols, maxCrowd }

    const randomRange = (min, max) => min + Math.random() * (max - min)
    const randomIndex = (array) => randomRange(0, array.length) | 0
    const removeFromArray = (array, i) => array.splice(i, 1)[0]
    const removeItemFromArray = (array, item) =>
      removeFromArray(array, array.indexOf(item))
    const removeRandomFromArray = (array) => removeFromArray(array, randomIndex(array))
    const getRandomFromArray = (array) => array[randomIndex(array) | 0]

    const resetPeep = ({ stage, peep }) => {
      let depthScale = UNIFORM_SCALE
      let scaledH = peep.height * depthScale
      const maxBodyH = stage.height * 0.9
      if (scaledH > maxBodyH) {
        depthScale = maxBodyH / peep.height
        scaledH = maxBodyH
      }

      peep.depthScale = depthScale
      peep.depthOpacity = UNIFORM_OPACITY

      const footLift = randomRange(FOOT_LIFT[0], FOOT_LIFT[1])
      const startY = Math.max(0, stage.height - scaledH - footLift)

      const direction = Math.random() > 0.5 ? 1 : -1
      let startX
      let endX
      const w = peep.width * depthScale

      if (direction === 1) {
        startX = -w
        endX = stage.width + w
        peep.scaleX = 1
      } else {
        startX = stage.width + w
        endX = -w
        peep.scaleX = -1
      }

      peep.x = startX + randomRange(-16, 16)
      peep.y = startY + randomRange(-2, 2)
      peep.anchorY = peep.y

      return { startY: peep.y, endX }
    }

    const normalWalk = ({ peep, props }) => {
      const { startY, endX } = props
      const xDuration = randomRange(9, 15)
      const yDuration = randomRange(0.22, 0.34)
      const bob = Math.min(randomRange(4, 7), startY)

      const tl = gsap.timeline()
      tl.timeScale(randomRange(0.8, 1.45))
      tl.to(peep, { duration: xDuration, x: endX, ease: 'none' }, 0)
      tl.to(
        peep,
        {
          duration: yDuration,
          repeat: Math.ceil(xDuration / yDuration),
          yoyo: true,
          y: startY - bob,
          ease: 'sine.inOut',
        },
        0,
      )

      return tl
    }

    const walks = [normalWalk]

    const createPeep = ({ image, rect }) => {
      const peep = {
        image,
        rect: [],
        width: 0,
        height: 0,
        x: 0,
        y: 0,
        anchorY: 0,
        scaleX: 1,
        depthScale: UNIFORM_SCALE,
        depthOpacity: UNIFORM_OPACITY,
        walk: null,
        setRect: (r) => {
          peep.rect = r
          peep.width = r[2]
          peep.height = r[3]
        },
        render: (c) => {
          const s = peep.depthScale
          c.save()
          c.translate(peep.x, peep.y)
          c.scale(peep.scaleX * s, s)
          c.globalAlpha = peep.depthOpacity
          c.drawImage(
            peep.image,
            peep.rect[0],
            peep.rect[1],
            peep.rect[2],
            peep.rect[3],
            0,
            0,
            peep.width,
            peep.height,
          )
          c.restore()
        },
      }
      peep.setRect(rect)
      return peep
    }

    const img = document.createElement('img')
    img.crossOrigin = 'anonymous'
    const stage = { width: 0, height: 0 }
    const allPeeps = []
    const availablePeeps = []
    const crowd = []
    let spawnTimers = []

    const createPeeps = () => {
      const { rows: r, cols: c } = config
      const { naturalWidth: width, naturalHeight: height } = img
      const total = r * c
      const rectWidth = width / r
      const rectHeight = height / c

      for (let i = 0; i < total; i++) {
        allPeeps.push(
          createPeep({
            image: img,
            rect: [
              (i % r) * rectWidth,
              ((i / r) | 0) * rectHeight,
              rectWidth,
              rectHeight,
            ],
          }),
        )
      }
    }

    const scheduleRespawn = () => {
      const t = gsap.delayedCall(randomRange(0.02, 0.15), () => {
        spawnOne()
        if (crowd.length < config.maxCrowd) scheduleRespawn()
      })
      spawnTimers.push(t)
    }

    const spawnOne = (instantProgress = true) => {
      if (!availablePeeps.length || crowd.length >= config.maxCrowd) return null

      const peep = removeRandomFromArray(availablePeeps)
      const walk = getRandomFromArray(walks)({
        peep,
        props: resetPeep({ peep, stage }),
      }).eventCallback('onComplete', () => {
        removePeepFromCrowd(peep)
        scheduleRespawn()
      })

      peep.walk = walk
      if (instantProgress) {
        walk.progress(randomRange(0.05, 0.95))
      }
      crowd.push(peep)
      crowd.sort((a, b) => a.anchorY - b.anchorY)
      return peep
    }

    const removePeepFromCrowd = (peep) => {
      removeItemFromArray(crowd, peep)
      availablePeeps.push(peep)
    }

    const initCrowd = () => {
      const target = Math.min(config.maxCrowd, allPeeps.length)
      for (let i = 0; i < target; i++) {
        spawnOne(true)
      }
    }

    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      ctx.save()
      ctx.scale(devicePixelRatio, devicePixelRatio)
      crowd.forEach((peep) => peep.render(ctx))
      ctx.restore()
    }

    const clearSpawnTimers = () => {
      spawnTimers.forEach((t) => t.kill())
      spawnTimers = []
    }

    const resize = () => {
      stage.width = canvas.clientWidth
      stage.height = canvas.clientHeight
      canvas.width = stage.width * devicePixelRatio
      canvas.height = stage.height * devicePixelRatio

      clearSpawnTimers()
      crowd.forEach((peep) => {
        if (peep.walk) peep.walk.kill()
      })

      crowd.length = 0
      availablePeeps.length = 0
      availablePeeps.push(...allPeeps)
      initCrowd()
    }

    const init = () => {
      createPeeps()
      resize()
      gsap.ticker.add(render)
    }

    img.onload = init
    img.onerror = () => {
      console.warn('[CrowdCanvas] Could not load sprite:', config.src)
    }
    img.src = config.src

    const handleResize = () => resize()
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      gsap.ticker.remove(render)
      clearSpawnTimers()
      crowd.forEach((peep) => {
        if (peep.walk) peep.walk.kill()
      })
    }
  }, [src, rows, cols, maxCrowd])

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className={`block h-full w-full ${className}`}
    />
  )
}
