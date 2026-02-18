'use client';

import { useMemo } from 'react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  Legend,
  Area,
  AreaChart
} from 'recharts';
import { format, subDays, startOfDay, parseISO } from 'date-fns';
import { BarChart3, PieChart as PieChartIcon, TrendingUp, Activity } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from './ui/Card';
import { StatBox } from './ui/StatBox';
import { formatEventType } from '../lib/utils';
import { ZONES } from '../lib/constants';

const CHART_COLORS = [
  '#3b82f6', // blue
  '#f97316', // orange
  '#22c55e', // green
  '#ef4444', // red
  '#a855f7', // purple
  '#06b6d4', // cyan
  '#f59e0b', // amber
  '#ec4899', // pink
];

const PRIORITY_CHART_COLORS = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#3b82f6',
};

export default function AnalyticsCharts({ analytics, incidents = [] }) {
  // Process data for charts
  const byTypeData = useMemo(() => {
    if (!analytics?.by_type) return [];
    return Object.entries(analytics.by_type)
      .map(([type, count]) => ({
        name: formatEventType(type),
        value: count,
        type,
      }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 8);
  }, [analytics]);

  const byZoneData = useMemo(() => {
    if (!analytics?.by_zone) return [];
    return Object.entries(analytics.by_zone)
      .map(([zone, count]) => {
        const zoneInfo = ZONES.find(z => z.id === zone) || { label: zone };
        return {
          name: zoneInfo.label,
          value: count,
          zone,
        };
      })
      .sort((a, b) => b.value - a.value);
  }, [analytics]);

  // Time trend data - incidents over past 7 days
  const trendData = useMemo(() => {
    const days = 7;
    const now = new Date();
    const data = [];
    
    for (let i = days - 1; i >= 0; i--) {
      const date = startOfDay(subDays(now, i));
      const nextDate = startOfDay(subDays(now, i - 1));
      
      const dayIncidents = incidents.filter(inc => {
        const ts = inc.event?.timestamp;
        if (!ts) return false;
        const incDate = new Date(ts > 1e12 ? ts : ts * 1000);
        return incDate >= date && incDate < nextDate;
      });
      
      const critical = dayIncidents.filter(inc => inc.alert?.priority === 'critical').length;
      const high = dayIncidents.filter(inc => inc.alert?.priority === 'high').length;
      const medium = dayIncidents.filter(inc => inc.alert?.priority === 'medium').length;
      const low = dayIncidents.filter(inc => inc.alert?.priority === 'low').length;
      
      data.push({
        date: format(date, 'EEE'),
        fullDate: format(date, 'MMM d'),
        total: dayIncidents.length,
        critical,
        high,
        medium,
        low,
      });
    }
    
    return data;
  }, [incidents]);

  // Priority distribution
  const priorityData = useMemo(() => {
    const counts = { critical: 0, high: 0, medium: 0, low: 0 };
    incidents.forEach(inc => {
      const priority = inc.alert?.priority || 'medium';
      if (counts[priority] !== undefined) counts[priority]++;
    });
    
    return Object.entries(counts)
      .filter(([_, count]) => count > 0)
      .map(([priority, count]) => ({
        name: priority.charAt(0).toUpperCase() + priority.slice(1),
        value: count,
        priority,
      }));
  }, [incidents]);

  // Summary stats
  const totalIncidents = analytics?.totals?.total || incidents.length;
  const todayIncidents = incidents.filter(inc => {
    const ts = inc.event?.timestamp;
    if (!ts) return false;
    const incDate = new Date(ts > 1e12 ? ts : ts * 1000);
    return incDate >= startOfDay(new Date());
  }).length;
  
  const avgPerDay = trendData.length > 0 
    ? Math.round(trendData.reduce((sum, d) => sum + d.total, 0) / trendData.length)
    : 0;
  
  const criticalCount = priorityData.find(p => p.priority === 'critical')?.value || 0;

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatBox
          label="Total Incidents"
          value={totalIncidents}
          icon={<Activity className="w-5 h-5" />}
          color="blue"
        />
        <StatBox
          label="Today"
          value={todayIncidents}
          icon={<TrendingUp className="w-5 h-5" />}
          color="green"
        />
        <StatBox
          label="Avg. Per Day"
          value={avgPerDay}
          icon={<BarChart3 className="w-5 h-5" />}
          color="purple"
        />
        <StatBox
          label="Critical"
          value={criticalCount}
          icon={<PieChartIcon className="w-5 h-5" />}
          color="red"
        />
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Incidents by Type - Bar Chart */}
        <Card>
          <CardHeader>
            <CardTitle icon={<BarChart3 className="w-4 h-4" />}>
              Incidents by Type
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={byTypeData} layout="vertical" margin={{ left: 20, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                  <XAxis type="number" stroke="var(--text-secondary)" fontSize={12} />
                  <YAxis 
                    dataKey="name" 
                    type="category" 
                    stroke="var(--text-secondary)" 
                    fontSize={11}
                    width={100}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--bg-secondary)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '8px',
                      color: 'var(--text-primary)',
                    }}
                  />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                    {byTypeData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Incidents by Zone - Pie Chart */}
        <Card>
          <CardHeader>
            <CardTitle icon={<PieChartIcon className="w-4 h-4" />}>
              Incidents by Zone
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={byZoneData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={2}
                    dataKey="value"
                  >
                    {byZoneData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--bg-secondary)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '8px',
                      color: 'var(--text-primary)',
                    }}
                  />
                  <Legend 
                    verticalAlign="bottom" 
                    height={36}
                    formatter={(value) => <span style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>{value}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Time Trend - Full Width */}
      <Card>
        <CardHeader>
          <CardTitle icon={<TrendingUp className="w-4 h-4" />}>
            Incident Trend (Last 7 Days)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trendData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                <XAxis 
                  dataKey="date" 
                  stroke="var(--text-secondary)" 
                  fontSize={12}
                  tickLine={false}
                />
                <YAxis 
                  stroke="var(--text-secondary)" 
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--bg-secondary)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '8px',
                    color: 'var(--text-primary)',
                  }}
                  labelFormatter={(label, payload) => payload[0]?.payload?.fullDate || label}
                />
                <Area
                  type="monotone"
                  dataKey="total"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorTotal)"
                  name="Total Incidents"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Priority Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Priority Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={priorityData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                  <XAxis 
                    dataKey="name" 
                    stroke="var(--text-secondary)" 
                    fontSize={12}
                    tickLine={false}
                  />
                  <YAxis 
                    stroke="var(--text-secondary)" 
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--bg-secondary)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '8px',
                      color: 'var(--text-primary)',
                    }}
                  />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {priorityData.map((entry) => (
                      <Cell 
                        key={`cell-${entry.priority}`} 
                        fill={PRIORITY_CHART_COLORS[entry.priority] || '#6b7280'} 
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Stacked Priority Trend */}
        <Card>
          <CardHeader>
            <CardTitle>Priority Trend</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trendData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                  <XAxis 
                    dataKey="date" 
                    stroke="var(--text-secondary)" 
                    fontSize={12}
                    tickLine={false}
                  />
                  <YAxis 
                    stroke="var(--text-secondary)" 
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--bg-secondary)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '8px',
                      color: 'var(--text-primary)',
                    }}
                  />
                  <Area type="monotone" dataKey="critical" stackId="1" stroke="#ef4444" fill="#ef4444" fillOpacity={0.6} name="Critical" />
                  <Area type="monotone" dataKey="high" stackId="1" stroke="#f97316" fill="#f97316" fillOpacity={0.6} name="High" />
                  <Area type="monotone" dataKey="medium" stackId="1" stroke="#eab308" fill="#eab308" fillOpacity={0.6} name="Medium" />
                  <Area type="monotone" dataKey="low" stackId="1" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.6} name="Low" />
                  <Legend 
                    verticalAlign="bottom" 
                    height={36}
                    formatter={(value) => <span style={{ color: 'var(--text-secondary)', fontSize: '11px' }}>{value}</span>}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
