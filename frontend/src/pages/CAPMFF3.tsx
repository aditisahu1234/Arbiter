export default function CAPMFF3() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-100">CAPM & Fama-French</h1>
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
        <p className="text-slate-400">
          Risk analysis with CAPM and India FF3 factors.
          <br />
          <span className="text-slate-500 text-sm">
            Note: FF3 factors are currently synthetic. Production requires IIM Ahmedabad data.
          </span>
        </p>
      </div>
    </div>
  )
}
