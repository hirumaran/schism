import { PaperBreakdown as PaperBreakdownType } from '@/lib/types'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'

interface PaperBreakdownProps {
  breakdown: PaperBreakdownType
}

export function PaperBreakdown({ breakdown }: PaperBreakdownProps) {
  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-4xl mx-auto px-4 py-8">
      {/* One line summary */}
      <div className="text-center space-y-4">
        <h2 className="text-3xl font-serif text-foreground leading-tight">
          {breakdown.one_line_summary}
        </h2>
      </div>

      {/* High level explanation */}
      <div className="p-6 bg-primary/5 border border-primary/10 rounded-xl">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-primary mb-3 flex items-center gap-2">
          <span>In plain English</span>
        </h3>
        <p className="text-lg text-foreground/90 leading-relaxed">
          {breakdown.high_level_explanation}
        </p>
      </div>

      {/* Two column layout for concepts and findings */}
      <div className="grid md:grid-cols-2 gap-8">
        {/* Core Concepts */}
        <div className="space-y-4">
          <h3 className="text-xl font-serif border-b pb-2">Core Concepts</h3>
          <Accordion type="single" collapsible className="w-full">
            {breakdown.core_concepts.map((concept, index) => (
              <AccordionItem key={index} value={`item-${index}`} className="border rounded-lg mb-2 bg-card px-1 shadow-sm">
                <AccordionTrigger className="hover:no-underline px-3 py-3 text-left">
                  <div>
                    <div className="font-semibold text-base">{concept.name}</div>
                    <div className="text-sm text-muted-foreground font-normal mt-1">{concept.plain_explanation}</div>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="px-3 pb-4 pt-1 text-sm space-y-3 text-foreground/80">
                  <div>
                    <strong className="text-foreground">Technical Details:</strong> {concept.technical_explanation}
                  </div>
                  <div>
                    <strong className="text-foreground">Why it matters:</strong> {concept.why_it_matters}
                  </div>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>

        <div className="space-y-8">
          {/* Key Findings */}
          <div className="space-y-4">
            <h3 className="text-xl font-serif border-b pb-2">Key Findings</h3>
            <ul className="space-y-3">
              {breakdown.key_findings.map((finding, i) => (
                <li key={i} className="flex gap-3 text-foreground/90">
                  <span className="flex-shrink-0 flex items-center justify-center w-6 h-6 rounded-full bg-secondary text-secondary-foreground text-xs font-medium">
                    {i + 1}
                  </span>
                  <span className="leading-snug">{finding}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Methodology */}
          <div className="space-y-4">
            <h3 className="text-xl font-serif border-b pb-2">Methodology</h3>
            <p className="text-foreground/80 leading-relaxed text-sm">
              {breakdown.methodology_summary}
            </p>
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-8 pt-4">
        {/* Limitations */}
        <div className="space-y-4">
          <h3 className="text-xl font-serif border-b pb-2 flex items-center gap-2">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-amber-500"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>
            Limitations
          </h3>
          <ul className="space-y-2">
            {breakdown.limitations.map((limitation, i) => (
              <li key={i} className="flex gap-2 text-sm text-muted-foreground">
                <span className="text-amber-500/70 mt-1">•</span>
                <span>{limitation}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Related Fields */}
        <div className="space-y-4">
          <h3 className="text-xl font-serif border-b pb-2">Related Fields</h3>
          <div className="flex flex-wrap gap-2">
            {breakdown.related_fields.map((field, i) => (
              <span key={i} className="px-3 py-1 bg-secondary/50 text-secondary-foreground border border-border rounded-full text-xs font-medium">
                {field}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
