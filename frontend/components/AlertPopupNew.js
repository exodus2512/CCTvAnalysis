'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { 
  X, 
  Eye, 
  Download, 
  CheckCircle, 
  ChevronDown, 
  ChevronUp,
  AlertTriangle,
  Clock,
  MapPin,
  Camera
} from 'lucide-react';
import { cn, formatTimestamp, formatRelativeTime, formatEventType, getEventType, getCameraId } from '../lib/utils';
import { PRIORITY_COLORS, ZONES } from '../lib/constants';
import { Badge } from './ui/Badge';
import { Button } from './ui/Button';

export default function AlertPopupNew({ alert, onDismiss, onResolve, compact = false }) {
  const [expanded, setExpanded] = useState(false);
  
  const event = alert?.event || alert || {};
  const priority = alert?.priority || 'medium';
  const eventType = getEventType(alert);
  const cameraId = getCameraId(alert);
  const zone = ZONES.find(z => z.id === event.zone) || { label: event.zone || 'Unknown' };
  const timestamp = event.timestamp;
  const summary = alert?.summary || '';
  const llmExplanation = alert?.llm_explanation || alert?.explanation || '';
  
  const colors = PRIORITY_COLORS[priority] || PRIORITY_COLORS.medium;

  if (compact) {
    return (
      <div className={cn(
        'p-3 rounded-lg border-l-4 transition-all',
        colors.border,
        colors.bg
      )}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className={cn('w-4 h-4', colors.text)} />
            <span className="text-sm font-medium text-foreground">
              {formatEventType(eventType)}
            </span>
          </div>
          <Badge variant={priority} size="sm">{priority}</Badge>
        </div>
        <div className="mt-1 text-xs text-muted-foreground">
          {formatRelativeTime(timestamp)}
        </div>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      className={cn(
        'rounded-xl border overflow-hidden transition-all',
        colors.border.replace('border-', 'border-l-4 border-'),
        'bg-card'
      )}
    >
      {/* Header */}
      <div className={cn('p-4', `bg-gradient-to-r ${colors.gradient}`)}>
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className={cn('p-2 rounded-lg', colors.bg)}>
              <AlertTriangle className={cn('w-5 h-5', colors.text)} />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">
                {formatEventType(eventType)}
              </h3>
              <div className="flex items-center gap-2 mt-1">
                <Badge variant={priority} size="sm">{priority}</Badge>
                <span className="text-xs text-muted-foreground">
                  {formatRelativeTime(timestamp)}
                </span>
              </div>
            </div>
          </div>
          
          <button
            onClick={onDismiss}
            className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Meta Info */}
      <div className="px-4 py-3 border-b border-border flex flex-wrap gap-4 text-xs">
        <MetaItem icon={Camera} label="Camera" value={cameraId} />
        <MetaItem icon={MapPin} label="Zone" value={zone.label} />
        <MetaItem icon={Clock} label="Time" value={formatTimestamp(timestamp)} />
      </div>

      {/* Summary */}
      {summary && (
        <div className="px-4 py-3 border-b border-border">
          <p className="text-sm text-foreground">{summary}</p>
        </div>
      )}

      {/* Expandable Details */}
      {llmExplanation && (
        <div className="border-b border-border">
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full px-4 py-2 flex items-center justify-between text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <span>AI Analysis</span>
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="px-4 pb-3"
            >
              <p className="text-sm text-muted-foreground bg-muted p-3 rounded-lg">
                {llmExplanation}
              </p>
            </motion.div>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="px-4 py-3 flex items-center gap-2">
        <Button
          variant="success"
          size="sm"
          onClick={onResolve}
          className="flex-1"
        >
          <CheckCircle className="w-4 h-4" />
          Mark Resolved
        </Button>
        <Button
          variant="secondary"
          size="sm"
        >
          <Eye className="w-4 h-4" />
          View
        </Button>
        <Button
          variant="secondary"
          size="sm"
        >
          <Download className="w-4 h-4" />
          PDF
        </Button>
      </div>
    </motion.div>
  );
}

function MetaItem({ icon: Icon, label, value }) {
  return (
    <div className="flex items-center gap-1.5">
      <Icon className="w-3.5 h-3.5 text-muted-foreground" />
      <span className="text-muted-foreground">{label}:</span>
      <span className="text-foreground font-medium">{value}</span>
    </div>
  );
}
