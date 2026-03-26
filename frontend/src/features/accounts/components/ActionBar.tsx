import { Button } from '@/components/ui/button'
import { Briefcase, Search, Send } from 'lucide-react'
import { toast } from 'sonner'

interface ActionBarProps {
  accountId: string
  accountName: string
}

export function ActionBar({ accountId: _accountId, accountName }: ActionBarProps) {
  return (
    <div className="flex items-center gap-3 py-4 border-t border-border mt-6">
      <Button
        variant="outline"
        onClick={() =>
          toast(`Coming soon -- Prep will generate a briefing for ${accountName}`)
        }
      >
        <Briefcase className="size-4 mr-1.5" />
        Prep
      </Button>
      <Button
        variant="outline"
        onClick={() =>
          toast(`Coming soon -- Research will enrich intel for ${accountName}`)
        }
      >
        <Search className="size-4 mr-1.5" />
        Research
      </Button>
      <Button
        variant="outline"
        onClick={() =>
          toast(`Coming soon -- Follow-up will draft outreach for ${accountName}`)
        }
      >
        <Send className="size-4 mr-1.5" />
        Follow-up
      </Button>
    </div>
  )
}
