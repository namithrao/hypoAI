import { useState } from 'react'
import { ChevronDown, ChevronUp, ExternalLink, FileText, Users, Calendar } from 'lucide-react'

interface AbstractSections {
  background?: string
  methods?: string
  results?: string
  conclusions?: string
}

interface FullTextSections {
  introduction?: string
  methods?: string
  results?: string
  discussion?: string
  conclusions?: string
}

interface PaperMetadata {
  pmid: string
  doi?: string
  title: string
  authors: string[]
  journal: string
  year: string
  keywords: string[]
  publication_types: string[]
  abstract: AbstractSections
  full_text?: FullTextSections
  pubmed_link: string
  pmc_link?: string
  doi_link?: string
  variables_extracted: string[]
  relevance: string
  key_findings: string
}

interface PaperCardProps {
  paper: PaperMetadata
}

export function PaperCard({ paper }: PaperCardProps) {
  const [expanded, setExpanded] = useState(false)

  const relevanceColors = {
    high: 'bg-green-600',
    medium: 'bg-yellow-600',
    low: 'bg-gray-600'
  }

  const relevanceColor = relevanceColors[paper.relevance as keyof typeof relevanceColors] || 'bg-gray-600'

  return (
    <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20 hover:border-white/40 transition-all">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="text-xl font-semibold text-white mb-2">{paper.title}</h3>
          <div className="flex flex-wrap items-center gap-3 text-sm text-gray-300">
            <div className="flex items-center gap-1">
              <Users className="w-4 h-4" />
              <span>{paper.authors.slice(0, 3).join(', ')}{paper.authors.length > 3 ? ' et al.' : ''}</span>
            </div>
            <div className="flex items-center gap-1">
              <FileText className="w-4 h-4" />
              <span>{paper.journal}</span>
            </div>
            <div className="flex items-center gap-1">
              <Calendar className="w-4 h-4" />
              <span>{paper.year}</span>
            </div>
          </div>
        </div>
        <span className={`${relevanceColor} text-white text-xs px-3 py-1 rounded-full font-semibold`}>
          {paper.relevance.toUpperCase()}
        </span>
      </div>

      {/* IDs and Links */}
      <div className="flex flex-wrap gap-3 mb-4">
        <span className="text-xs bg-blue-600 text-white px-3 py-1 rounded font-mono">
          PMID: {paper.pmid}
        </span>
        {paper.doi && (
          <span className="text-xs bg-purple-600 text-white px-3 py-1 rounded font-mono">
            DOI: {paper.doi}
          </span>
        )}
        <a
          href={paper.pubmed_link}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded flex items-center gap-1 transition-colors"
        >
          PubMed <ExternalLink className="w-3 h-3" />
        </a>
        {paper.pmc_link && (
          <a
            href={paper.pmc_link}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs bg-green-500 hover:bg-green-600 text-white px-3 py-1 rounded flex items-center gap-1 transition-colors"
          >
            PMC Full Text <ExternalLink className="w-3 h-3" />
          </a>
        )}
        {paper.doi_link && (
          <a
            href={paper.doi_link}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs bg-purple-500 hover:bg-purple-600 text-white px-3 py-1 rounded flex items-center gap-1 transition-colors"
          >
            DOI Link <ExternalLink className="w-3 h-3" />
          </a>
        )}
      </div>

      {/* Keywords */}
      {paper.keywords.length > 0 && (
        <div className="mb-4">
          <p className="text-xs text-gray-400 mb-2">Keywords:</p>
          <div className="flex flex-wrap gap-2">
            {paper.keywords.map((keyword, i) => (
              <span key={i} className="text-xs bg-slate-700 text-gray-300 px-2 py-1 rounded">
                {keyword}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Variables Extracted */}
      {paper.variables_extracted.length > 0 && (
        <div className="mb-4">
          <p className="text-xs text-gray-400 mb-2">Variables Extracted:</p>
          <div className="flex flex-wrap gap-2">
            {paper.variables_extracted.map((variable, i) => (
              <span key={i} className="text-xs bg-blue-800 text-blue-200 px-2 py-1 rounded font-semibold">
                {variable}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Key Findings */}
      {paper.key_findings && (
        <div className="mb-4 p-3 bg-slate-800/50 rounded-lg">
          <p className="text-sm text-gray-300">
            <span className="font-semibold text-gray-200">Key Findings: </span>
            {paper.key_findings}
          </p>
        </div>
      )}

      {/* Expand/Collapse Button */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-center gap-2 py-2 bg-slate-700/50 hover:bg-slate-700 text-gray-300 rounded-lg transition-colors"
      >
        {expanded ? (
          <>
            <ChevronUp className="w-5 h-5" />
            Hide Details
          </>
        ) : (
          <>
            <ChevronDown className="w-5 h-5" />
            Show Abstract & Full Text
          </>
        )}
      </button>

      {/* Expanded Content */}
      {expanded && (
        <div className="mt-4 space-y-4">
          {/* Abstract Sections */}
          <div className="border-t border-gray-700 pt-4">
            <h4 className="text-lg font-semibold text-white mb-3">Abstract</h4>
            <div className="space-y-3">
              {paper.abstract.background && (
                <div>
                  <p className="text-sm font-semibold text-blue-300 mb-1">Background</p>
                  <p className="text-sm text-gray-300">{paper.abstract.background}</p>
                </div>
              )}
              {paper.abstract.methods && (
                <div>
                  <p className="text-sm font-semibold text-green-300 mb-1">Methods</p>
                  <p className="text-sm text-gray-300">{paper.abstract.methods}</p>
                </div>
              )}
              {paper.abstract.results && (
                <div>
                  <p className="text-sm font-semibold text-yellow-300 mb-1">Results</p>
                  <p className="text-sm text-gray-300">{paper.abstract.results}</p>
                </div>
              )}
              {paper.abstract.conclusions && (
                <div>
                  <p className="text-sm font-semibold text-purple-300 mb-1">Conclusions</p>
                  <p className="text-sm text-gray-300">{paper.abstract.conclusions}</p>
                </div>
              )}
            </div>
          </div>

          {/* Full Text Sections (if available) */}
          {paper.full_text && (
            <div className="border-t border-gray-700 pt-4">
              <h4 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                Full Text
                <span className="text-xs bg-green-600 text-white px-2 py-1 rounded">Available</span>
              </h4>
              <div className="space-y-3">
                {paper.full_text.introduction && (
                  <div>
                    <p className="text-sm font-semibold text-blue-300 mb-1">Introduction</p>
                    <p className="text-sm text-gray-300">{paper.full_text.introduction}</p>
                  </div>
                )}
                {paper.full_text.methods && (
                  <div>
                    <p className="text-sm font-semibold text-green-300 mb-1">Methods</p>
                    <p className="text-sm text-gray-300">{paper.full_text.methods}</p>
                  </div>
                )}
                {paper.full_text.results && (
                  <div>
                    <p className="text-sm font-semibold text-yellow-300 mb-1">Results</p>
                    <p className="text-sm text-gray-300">{paper.full_text.results}</p>
                  </div>
                )}
                {paper.full_text.discussion && (
                  <div>
                    <p className="text-sm font-semibold text-orange-300 mb-1">Discussion</p>
                    <p className="text-sm text-gray-300">{paper.full_text.discussion}</p>
                  </div>
                )}
                {paper.full_text.conclusions && (
                  <div>
                    <p className="text-sm font-semibold text-purple-300 mb-1">Conclusions</p>
                    <p className="text-sm text-gray-300">{paper.full_text.conclusions}</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
