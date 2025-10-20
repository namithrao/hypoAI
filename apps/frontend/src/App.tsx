import { useState } from 'react'
import { Brain, Search, Database, AlertTriangle, CheckCircle, FileText, Calendar, Info } from 'lucide-react'
import axios from 'axios'

interface ResearchResponse {
  success: boolean
  hypothesis: string
  feasible: boolean
  reasoning: string
  data_files: Array<{
    category: string
    file_name: string
    description: string
    cycles: string[]
  }>
  variables: Array<{
    variable_name: string
    description: string
    file_name: string
    file_code: string
    category: string
    unit: string | null
    cycles: string[]
  }>
  recommended_cycles: string[]
  warnings: string[]
  metadata: {
    num_files: number
    num_variables: number
    num_cycles: number
    conversation_turns: number
  }
}

function App() {
  const [hypothesis, setHypothesis] = useState('')
  const [result, setResult] = useState<ResearchResponse | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runResearch = async () => {
    if (!hypothesis.trim()) {
      alert('Please enter a research hypothesis')
      return
    }

    setIsRunning(true)
    setError(null)
    setResult(null)

    try {
      const response = await axios.post<ResearchResponse>('/api/research', {
        hypothesis,
        max_iterations: 10
      })

      setResult(response.data)
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'Unknown error occurred'
      setError(errorMsg)
    } finally {
      setIsRunning(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-white mb-4">
            SynthAI MCP Research System
          </h1>
          <p className="text-xl text-blue-200">
            AI-powered NHANES data research using Model Context Protocol
          </p>
        </div>

        {/* Input Section */}
        <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 mb-8 border border-white/20">
          <label className="block text-white text-lg font-semibold mb-4">
            Research Question
          </label>
          <textarea
            value={hypothesis}
            onChange={(e) => setHypothesis(e.target.value)}
            placeholder="e.g., Does elevated CRP predict cardiovascular events in adults aged 40-65?"
            className="w-full h-32 px-4 py-3 bg-slate-800/50 text-white border border-blue-400/30 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none placeholder-gray-400"
          />
          <button
            onClick={runResearch}
            disabled={isRunning}
            className="mt-4 px-8 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white rounded-lg font-semibold flex items-center gap-2 transition-colors"
          >
            <Search className="w-5 h-5" />
            {isRunning ? 'Analyzing...' : 'Analyze with NHANES Data'}
          </button>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-900/30 border border-red-500 rounded-2xl p-6 mb-8">
            <div className="flex items-center gap-3 mb-2">
              <AlertTriangle className="w-6 h-6 text-red-400" />
              <h3 className="text-xl font-semibold text-red-300">Error</h3>
            </div>
            <p className="text-red-200">{error}</p>
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="space-y-6">
            {/* Feasibility Status */}
            <div className={`rounded-2xl p-6 border ${
              result.feasible
                ? 'bg-green-900/20 border-green-500'
                : 'bg-yellow-900/20 border-yellow-500'
            }`}>
              <div className="flex items-center gap-3 mb-3">
                {result.feasible ? (
                  <CheckCircle className="w-8 h-8 text-green-400" />
                ) : (
                  <AlertTriangle className="w-8 h-8 text-yellow-400" />
                )}
                <h2 className="text-2xl font-bold text-white">
                  {result.feasible ? 'Research Feasible' : 'Limited Feasibility'}
                </h2>
              </div>
              <p className={`text-lg ${result.feasible ? 'text-green-200' : 'text-yellow-200'}`}>
                {result.reasoning}
              </p>
            </div>

            {/* Warnings */}
            {result.warnings.length > 0 && (
              <div className="bg-yellow-900/20 border border-yellow-500 rounded-2xl p-6">
                <h3 className="text-xl font-semibold text-yellow-300 mb-4 flex items-center gap-2">
                  <AlertTriangle className="w-6 h-6" />
                  Warnings
                </h3>
                <ul className="space-y-2">
                  {result.warnings.map((warning, i) => (
                    <li key={i} className="text-yellow-200 pl-4 border-l-2 border-yellow-500">
                      {warning}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Summary Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6 border border-white/20">
                <FileText className="w-8 h-8 text-blue-400 mb-2" />
                <p className="text-3xl font-bold text-white">{result.metadata.num_files}</p>
                <p className="text-gray-300">Data Files</p>
              </div>
              <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6 border border-white/20">
                <Database className="w-8 h-8 text-purple-400 mb-2" />
                <p className="text-3xl font-bold text-white">{result.metadata.num_variables}</p>
                <p className="text-gray-300">Variables</p>
              </div>
              <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6 border border-white/20">
                <Calendar className="w-8 h-8 text-green-400 mb-2" />
                <p className="text-3xl font-bold text-white">{result.metadata.num_cycles}</p>
                <p className="text-gray-300">NHANES Cycles</p>
              </div>
              <div className="bg-white/10 backdrop-blur-lg rounded-xl p-6 border border-white/20">
                <Brain className="w-8 h-8 text-orange-400 mb-2" />
                <p className="text-3xl font-bold text-white">{result.metadata.conversation_turns}</p>
                <p className="text-gray-300">AI Iterations</p>
              </div>
            </div>

            {/* Data Files */}
            {result.data_files.length > 0 && (
              <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20">
                <h3 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                  <FileText className="w-6 h-6 text-blue-400" />
                  NHANES Data Files ({result.data_files.length})
                </h3>
                <div className="space-y-3">
                  {result.data_files.map((file, i) => (
                    <div key={i} className="bg-slate-800/50 p-4 rounded-lg">
                      <div className="flex items-start justify-between mb-2">
                        <p className="text-white font-semibold">{file.file_name}</p>
                        <span className="text-xs bg-blue-600 text-white px-2 py-1 rounded">
                          {file.category}
                        </span>
                      </div>
                      <p className="text-gray-300 text-sm mb-2">{file.description}</p>
                      <p className="text-gray-400 text-xs">
                        Cycles: {file.cycles.join(', ')}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Variables */}
            {result.variables.length > 0 && (
              <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20">
                <h3 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                  <Database className="w-6 h-6 text-purple-400" />
                  NHANES Variables ({result.variables.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="border-b border-gray-600">
                        <th className="px-4 py-2 text-gray-300">Variable</th>
                        <th className="px-4 py-2 text-gray-300">Description</th>
                        <th className="px-4 py-2 text-gray-300">File</th>
                        <th className="px-4 py-2 text-gray-300">Unit</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.variables.map((variable, i) => (
                        <tr key={i} className="border-b border-gray-700">
                          <td className="px-4 py-3 text-blue-300 font-mono text-sm">
                            {variable.variable_name}
                          </td>
                          <td className="px-4 py-3 text-gray-200 text-sm">
                            {variable.description}
                          </td>
                          <td className="px-4 py-3 text-gray-300 text-sm">
                            {variable.file_name}
                          </td>
                          <td className="px-4 py-3 text-gray-400 text-sm">
                            {variable.unit || 'N/A'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Recommended Cycles */}
            {result.recommended_cycles.length > 0 && (
              <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20">
                <h3 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
                  <Calendar className="w-6 h-6 text-green-400" />
                  Recommended NHANES Cycles
                </h3>
                <div className="flex flex-wrap gap-3">
                  {result.recommended_cycles.map((cycle, i) => (
                    <span key={i} className="bg-green-600 text-white px-4 py-2 rounded-lg font-semibold">
                      {cycle}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default App
