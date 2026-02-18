'use client';

import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Search, 
  Filter,
  Download,
  CheckCircle,
  Clock,
  Camera,
  MapPin,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  X
} from 'lucide-react';
import { cn, formatTimestamp, formatRelativeTime, formatEventType, getPriorityLevel } from '../lib/utils';
import { ZONES, PRIORITY_COLORS, EVENT_LABELS } from '../lib/constants';
import { Badge } from './ui/Badge';
import { Button } from './ui/Button';
import { Input, Select } from './ui/Input';
import { NoIncidents, NoSearchResults } from './ui/EmptyState';

const ITEMS_PER_PAGE = 15;

export default function IncidentTimeline({ incidents = [], onResolve, compact = false }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedZone, setSelectedZone] = useState('all');
  const [selectedType, setSelectedType] = useState('all');
  const [selectedPriority, setSelectedPriority] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [showFilters, setShowFilters] = useState(false);

  // Get unique event types from incidents
  const eventTypes = useMemo(() => {
    const types = new Set();
    incidents.forEach(inc => {
      const type = inc.event?.event_type;
      if (type) types.add(type);
    });
    return Array.from(types);
  }, [incidents]);

  // Filter incidents
  const filteredIncidents = useMemo(() => {
    return incidents.filter(inc => {
      const event = inc.event || {};
      const alert = inc.alert || {};
      
      // Search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const matchesType = event.event_type?.toLowerCase().includes(query);
        const matchesCamera = event.camera_id?.toLowerCase().includes(query);
        const matchesZone = event.zone?.toLowerCase().includes(query);
        const matchesSummary = alert.summary?.toLowerCase().includes(query);
        
        if (!matchesType && !matchesCamera && !matchesZone && !matchesSummary) {
          return false;
        }
      }
      
      // Zone filter
      if (selectedZone !== 'all' && event.zone !== selectedZone) {
        return false;
      }
      
      // Type filter
      if (selectedType !== 'all' && event.event_type !== selectedType) {
        return false;
      }
      
      // Priority filter
      if (selectedPriority !== 'all' && alert.priority !== selectedPriority) {
        return false;
      }
      
      return true;
    });
  }, [incidents, searchQuery, selectedZone, selectedType, selectedPriority]);

  // Pagination
  const totalPages = Math.ceil(filteredIncidents.length / ITEMS_PER_PAGE);
  const paginatedIncidents = useMemo(() => {
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    return filteredIncidents.slice(start, start + ITEMS_PER_PAGE);
  }, [filteredIncidents, currentPage]);

  // Reset to page 1 when filters change
  const handleFilterChange = (setter) => (value) => {
    setter(value);
    setCurrentPage(1);
  };

  const clearFilters = () => {
    setSearchQuery('');
    setSelectedZone('all');
    setSelectedType('all');
    setSelectedPriority('all');
    setCurrentPage(1);
  };

  const hasFilters = searchQuery || selectedZone !== 'all' || selectedType !== 'all' || selectedPriority !== 'all';

  if (incidents.length === 0) {
    return <NoIncidents />;
  }

  return (
    <div className="space-y-4">
      {/* Search & Filter Bar */}
      {!compact && (
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search incidents..."
                value={searchQuery}
                onChange={(e) => handleFilterChange(setSearchQuery)(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-background border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50"
              />
            </div>
            
            <Button 
              variant={showFilters ? 'primary' : 'secondary'}
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
            >
              <Filter className="w-4 h-4" />
              Filters
              {hasFilters && (
                <span className="w-2 h-2 rounded-full bg-blue-400" />
              )}
            </Button>

            {hasFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                <X className="w-4 h-4" />
                Clear
              </Button>
            )}
          </div>

          {/* Filter Options */}
          <AnimatePresence>
            {showFilters && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 p-4 bg-muted rounded-lg">
                  <Select
                    label="Zone"
                    value={selectedZone}
                    onChange={(e) => handleFilterChange(setSelectedZone)(e.target.value)}
                    options={[
                      { value: 'all', label: 'All Zones' },
                      ...ZONES.filter(z => z.id !== 'all').map(z => ({
                        value: z.id,
                        label: z.label
                      }))
                    ]}
                  />
                  
                  <Select
                    label="Event Type"
                    value={selectedType}
                    onChange={(e) => handleFilterChange(setSelectedType)(e.target.value)}
                    options={[
                      { value: 'all', label: 'All Types' },
                      ...eventTypes.map(type => ({
                        value: type,
                        label: formatEventType(type)
                      }))
                    ]}
                  />
                  
                  <Select
                    label="Priority"
                    value={selectedPriority}
                    onChange={(e) => handleFilterChange(setSelectedPriority)(e.target.value)}
                    options={[
                      { value: 'all', label: 'All Priorities' },
                      { value: 'critical', label: 'Critical' },
                      { value: 'high', label: 'High' },
                      { value: 'medium', label: 'Medium' },
                      { value: 'low', label: 'Low' },
                    ]}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* Results Summary */}
      {!compact && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            Showing {paginatedIncidents.length} of {filteredIncidents.length} incidents
          </span>
          <Button variant="secondary" size="sm">
            <Download className="w-4 h-4" />
            Export
          </Button>
        </div>
      )}

      {/* Incidents List */}
      {paginatedIncidents.length === 0 ? (
        <NoSearchResults query={searchQuery} />
      ) : (
        <div className="space-y-2">
          {paginatedIncidents.map((incident, idx) => (
            <IncidentRow
              key={incident.id || idx}
              incident={incident}
              onResolve={onResolve}
              compact={compact}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {!compact && totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-4">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage === 1}
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>
          
          <div className="flex items-center gap-1">
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              let pageNum;
              if (totalPages <= 5) {
                pageNum = i + 1;
              } else if (currentPage <= 3) {
                pageNum = i + 1;
              } else if (currentPage >= totalPages - 2) {
                pageNum = totalPages - 4 + i;
              } else {
                pageNum = currentPage - 2 + i;
              }
              
              return (
                <button
                  key={pageNum}
                  onClick={() => setCurrentPage(pageNum)}
                  className={cn(
                    'w-8 h-8 rounded-lg text-sm font-medium transition-colors',
                    pageNum === currentPage
                      ? 'bg-blue-500 text-white'
                      : 'text-muted-foreground hover:bg-muted'
                  )}
                >
                  {pageNum}
                </button>
              );
            })}
          </div>
          
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      )}
    </div>
  );
}

function IncidentRow({ incident, onResolve, compact }) {
  const event = incident.event || {};
  const alert = incident.alert || {};
  const priority = alert.priority || 'medium';
  const colors = PRIORITY_COLORS[priority] || PRIORITY_COLORS.medium;
  const zone = ZONES.find(z => z.id === event.zone) || { label: event.zone || 'Unknown' };

  if (compact) {
    return (
      <div className={cn('flex items-center gap-3 py-2 px-3 rounded-lg', colors.bg)}>
        <Badge variant={priority} size="sm" dot>{priority}</Badge>
        <span className="text-sm font-medium text-foreground flex-1">
          {formatEventType(event.event_type)}
        </span>
        <span className="text-xs text-muted-foreground">
          {formatRelativeTime(event.timestamp)}
        </span>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        'flex items-center gap-4 p-4 rounded-xl border transition-colors',
        'bg-card border-border hover:border-border-hover',
        incident.resolved && 'opacity-60'
      )}
    >
      {/* Priority Indicator */}
      <div className={cn('w-1 h-12 rounded-full', colors.dot)} />

      {/* Icon */}
      <div className={cn('p-2 rounded-lg', colors.bg)}>
        <AlertTriangle className={cn('w-5 h-5', colors.text)} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-medium text-foreground">
            {formatEventType(event.event_type)}
          </span>
          <Badge variant={priority} size="sm">{priority}</Badge>
          {incident.resolved && (
            <Badge variant="success" size="sm">Resolved</Badge>
          )}
        </div>
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <Camera className="w-3 h-3" /> {event.camera_id || 'Unknown'}
          </span>
          <span className="flex items-center gap-1">
            <MapPin className="w-3 h-3" /> {zone.label}
          </span>
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" /> {formatRelativeTime(event.timestamp)}
          </span>
        </div>
        {alert.summary && (
          <p className="text-sm text-muted-foreground mt-1 truncate">
            {alert.summary}
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {!incident.resolved && onResolve && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onResolve(incident.id)}
          >
            <CheckCircle className="w-4 h-4" />
          </Button>
        )}
        {alert.pdf_url && (
          <Button
            variant="ghost"
            size="sm"
            as="a"
            href={alert.pdf_url}
            target="_blank"
          >
            <Download className="w-4 h-4" />
          </Button>
        )}
      </div>
    </motion.div>
  );
}
