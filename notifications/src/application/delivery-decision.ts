/**
 * The outcome of processing one message, expressed in transport-agnostic terms.
 * The use case returns one of these; the messaging adapter maps it onto broker
 * actions (ack / nack-to-retry / publish-to-DLQ). Keeping this an enum of plain
 * data keeps the use case free of any RabbitMQ types.
 */

/** Why a message was routed to the dead-letter queue (bounded set for metrics). */
export type DeadLetterCategory =
  | 'invalid-payload' // failed structural (schema) validation
  | 'validation' // failed a domain invariant
  | 'permanent' // transport rejected it permanently
  | 'exhausted' // ran out of retry attempts
  | 'unexpected'; // an unforeseen error

export type DeliveryDecision =
  | { readonly type: 'ack' }
  | { readonly type: 'retry' }
  | {
      readonly type: 'dead-letter';
      readonly category: DeadLetterCategory;
      readonly reason: string;
    };

export const ackDecision = (): DeliveryDecision => ({ type: 'ack' });

export const retryDecision = (): DeliveryDecision => ({ type: 'retry' });

export const deadLetterDecision = (
  category: DeadLetterCategory,
  reason: string,
): DeliveryDecision => ({ type: 'dead-letter', category, reason });
