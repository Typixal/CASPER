import PredictionRamp from "./charts/PredictionRamp"

export default function Hero({ prediction }) {
  return (
    <section className="px-4 pt-6 sm:px-6">
      <PredictionRamp prediction={prediction} />
    </section>
  )
}
