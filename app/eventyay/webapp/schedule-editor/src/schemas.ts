import { z } from 'zod';
z.config({ jitless: true });

// Helper function to transform title to a record
const toTitleRecord = (val: unknown): Record<string, string> => {
  if (val !== null && typeof val === 'object' && !Array.isArray(val)) {
    const record = Object.fromEntries(
      Object.entries(val as Record<string, unknown>).map(([key, value]) => [
        key,
        value == null ? '' : String(value),
      ])
    );
    return Object.keys(record).length > 0 ? record : { en: '' };
  }
  if (typeof val === 'string') {
    return { en: val };
  }
  return { en: '' };
};

const LocalizedTextSchema = z.unknown().transform(toTitleRecord);

const NullableTextSchema = z.string().nullable().optional().transform(val => val ?? '');

const SpeakerReferenceSchema = z.union([
  z.string(),
  z.null(),
  z.object({
    name: z.string().nullable().optional(),
    code: z.string().nullable().optional(),
  }).passthrough(),
]);

const toSpeakerReference = (val: z.infer<typeof SpeakerReferenceSchema>): string | undefined => {
  if (typeof val === 'string') return val;
  if (!val) return undefined;
  return val.code ?? undefined;
};

export const SpeakerSchema = z.object({
  code: z.string().nullable().optional(),
  name: z.string().nullable().transform(val => val ?? ''),
});

export const RoomSchema = z.object({
  id: z.number(),
  name: LocalizedTextSchema,
  description: LocalizedTextSchema
});

export const TrackSchema = z.object({
  id: z.number(),
  name: LocalizedTextSchema,
  color: z.string().nullable().optional()
});

// Define availability entry schema
const AvailabilityEntrySchema = z.object({
  start: z.string(),
  end: z.string()
});

export const TalkSchema = z.object({
  id: z.number(),
  code: z.string().optional(),
  title: LocalizedTextSchema,
  abstract: NullableTextSchema,
  description: NullableTextSchema,
  speakers: z.array(SpeakerReferenceSchema).transform(val => {
    return val
      .map(toSpeakerReference)
      .filter((speaker): speaker is string => typeof speaker === 'string' && speaker.length > 0);
  }).optional().default([]),
  room: z.union([
    z.number(),
    z.string().transform(val => parseInt(val, 10) || 0)
  ]).nullable().optional(),
  track: z.union([
    z.number(),
    z.string().transform(val => parseInt(val, 10) || 0),
    z.object({ id: z.any() }).passthrough().transform(val => Number(val.id))
  ]).nullable().optional(),
  start: z.string().nullable().optional(),
  end: z.string().nullable().optional(),
  state: z.string().optional(),
  updated: z.string().optional(),
  uncreated: z.boolean().optional(),
  availabilities: z.array(AvailabilityEntrySchema).optional().default([]),
  duration: z.number().optional()
});

export const WarningSchema = z.object({
  message: z.string(),
});

const WarningRecordSchema = z.record(z.string(), z.array(WarningSchema));

export const ScheduleSchema = z.object({
  version: z.nullable(z.string().nullable()),
  event_start: z.string(),
  event_end: z.string(),
  timezone: z.string(),
  locales: z.array(z.string()).default([]),
  rooms: z.array(RoomSchema).default([]),
  tracks: z.array(TrackSchema).default([]),
  speakers: z.array(SpeakerSchema).default([]),
  talks: z.array(TalkSchema).default([]),
  now: z.string().optional(),
  warnings: WarningRecordSchema.optional().default({})
});

export const AvailabilitySchema = z.object({
  rooms: z.record(z.string(), z.array(AvailabilityEntrySchema)).optional(),
  talks: z.record(z.string(), z.array(AvailabilityEntrySchema)).optional(),
});

export const WarningsSchema = z.record(z.string(), z.array(WarningSchema)).optional();

// Inferred types
export type AvailabilityEntry = z.infer<typeof AvailabilityEntrySchema>;
export type Speaker = z.infer<typeof SpeakerSchema>;
export type Room = z.infer<typeof RoomSchema>;
export type Track = z.infer<typeof TrackSchema>;
export type Talk = z.infer<typeof TalkSchema>;
export type Schedule = z.infer<typeof ScheduleSchema>;
export type Availability = z.infer<typeof AvailabilitySchema>;
export type Warnings = z.infer<typeof WarningsSchema>;
