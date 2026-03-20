const steps = [
  'Worker registers with email and role',
  'ML model predicts disruption risk score',
  'System calculates weekly premium automatically',
  'Live weather monitor tracks rainfall and AQI',
  'Rainfall threshold breach auto-triggers claim',
  'Worker receives payout notification instantly',
]

export default function HowItWorksPage() {
  return (
    <div className="mx-auto max-w-5xl px-6 pb-20 pt-14 sm:px-10">
      <div className="glass rounded-3xl p-8 sm:p-10">
        <h1 className="font-outfit text-4xl font-bold text-slate-800">How GigCover AI Works</h1>
        <p className="mt-3 text-slate-700">
          Parametric insurance means payout triggers are based on external data, not manual claim paperwork.
        </p>

        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          {steps.map((step, index) => (
            <div key={step} className="rounded-2xl bg-white/70 p-4 shadow-sm transition hover:-translate-y-1">
              <p className="font-space text-sm font-semibold text-slate-500">STEP {index + 1}</p>
              <p className="mt-2 text-slate-800">{step}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
