/** Keep native workflow state separate from legacy HTTP-success semantics. */
import type { AgentActionConfirmResult } from '@/api'
import type { ActionWorkflowReceipt, OrderAction } from '@/types/api'

function hasWorkflowError(workflow: ActionWorkflowReceipt): boolean {
  return !!workflow.error && Object.keys(workflow.error).length > 0
}

/** A stale local CONFIRMED flag is never stronger than a native nonterminal/error. */
export function actionDisplayStatus(action: OrderAction): OrderAction['status'] {
  if (['CONFIRMING', 'CANCELLING', 'RECOVERING'].includes(action.status || '')) return action.status
  const workflow = action.workflow
  // Canonical waiting reconciliation terminates with a diagnostic, not a retryable failure.
  if (workflow?.workflowStatus === 'EXPIRED' || workflow?.workflowStatus === 'CANCELLED') return workflow.workflowStatus
  if (action.recoveryRequired) return 'RECOVERY_REQUIRED'
  if (!workflow) return action.nativeManaged === true ? 'RECOVERY_REQUIRED' : action.status
  if (hasWorkflowError(workflow)) return workflow.recoverable ? 'RECOVERY_REQUIRED' : 'FAILED'
  switch (workflow.workflowStatus) {
    case 'WAITING_APPROVAL': return action.status === 'PENDING' || action.status === 'EXPIRED' ? action.status : 'RECOVERY_REQUIRED'
    case 'EXECUTING': return 'EXECUTING'
    case 'FAILED': return 'FAILED'
    case 'EXPIRED': return 'EXPIRED'
    case 'CANCELLED': return 'CANCELLED'
    case 'COMPLETED': return action.status === 'CONFIRMED' ? 'CONFIRMED' : 'RECOVERY_REQUIRED'
    default: return 'RECOVERY_REQUIRED'
  }
}

export function canDecideAction(action: OrderAction): boolean {
  const workflow = action.workflow
  return (action.status === 'PENDING' || action.status === 'FAILED') && !action.recoveryRequired
    && (workflow ? workflow.nativeInterrupt === true && workflow.workflowStatus === 'WAITING_APPROVAL'
      && !hasWorkflowError(workflow) && action.status === 'PENDING' : action.nativeManaged !== true)
}

export function canRecoverAction(action: OrderAction): boolean {
  if (['CONFIRMING', 'CANCELLING', 'RECOVERING', 'CONFIRMED', 'CANCELLED', 'EXPIRED'].includes(actionDisplayStatus(action) || '')) return false
  return actionDisplayStatus(action) === 'RECOVERY_REQUIRED' || !!(action.workflow && (
    ['WAITING_APPROVAL', 'EXECUTING'].includes(action.workflow.workflowStatus) || action.workflow.recoverable))
}

function requireRecovery(action: OrderAction) {
  action.recoveryRequired = true
  action.status = 'RECOVERY_REQUIRED'
}

/** True means native/ambiguous: the caller MUST NOT apply legacy success logic. */
export function applyWorkflowReceipt(action: OrderAction, result?: AgentActionConfirmResult, recovery = false): boolean {
  const workflow = result?.workflow
  if (!workflow && !action.workflow && action.nativeManaged !== true && !action.recoveryRequired && !recovery) return false
  if (!workflow || workflow.actionId !== action.actionId || workflow.nativeInterrupt !== true
    || typeof workflow.recoverable !== 'boolean' || typeof workflow.interrupted !== 'boolean'
    || !['WAITING_APPROVAL', 'EXECUTING', 'COMPLETED', 'CANCELLED', 'FAILED', 'EXPIRED'].includes(workflow.workflowStatus)) {
    requireRecovery(action)
    return true
  }
  action.nativeManaged = true
  action.workflow = { ...workflow }
  action.recoveryRequired = false
  if (workflow.workflowStatus === 'EXPIRED' || workflow.workflowStatus === 'CANCELLED') {
    action.status = workflow.workflowStatus
  } else if (hasWorkflowError(workflow)) {
    action.status = workflow.recoverable ? 'RECOVERY_REQUIRED' : 'FAILED'
    action.recoveryRequired = workflow.recoverable
  } else if (workflow.workflowStatus === 'WAITING_APPROVAL') {
    action.status = 'PENDING'
  } else if (workflow.workflowStatus === 'EXECUTING') {
    action.status = 'EXECUTING'
  } else if (workflow.workflowStatus === 'COMPLETED') {
    if (result?.type !== action.type || result.actionStatus !== 'CONFIRMED'
      || !Number.isSafeInteger(result.orderId) || (result.orderId || 0) <= 0 || !result.orderNo
      || (action.type === 'ORDER_CREATE' && (!result.receiverName || !result.receiverPhone || !result.receiverAddress))
      || (action.type === 'AFTER_SALE_APPLY' && (!result.afterSaleId || !result.afterSaleNo))) {
      requireRecovery(action)
      return true
    }
    Object.assign(action, {
      status: 'CONFIRMED', orderId: result.orderId, orderNo: result.orderNo,
      amount: result.totalAmount ?? action.amount, orderStatus: result.status,
      afterSaleId: result.afterSaleId, afterSaleNo: result.afterSaleNo,
      ...(action.type === 'ORDER_CREATE' ? {
        receiverName: result.receiverName, receiverPhone: result.receiverPhone, receiverAddress: result.receiverAddress,
      } : {}),
    })
  } else {
    action.status = workflow.workflowStatus as 'CANCELLED' | 'FAILED' | 'EXPIRED'
  }
  return true
}

export function failActionRequest(action: OrderAction, error: unknown) {
  const failure = error as { code?: number } | undefined
  // Enabled preparations carry workflow provenance. Native/gateway failures may
  // already have a durable decision; legacy cards retain their explicit retry UI.
  if (action.workflow || failure?.code === 5002) action.nativeManaged = true
  if (action.nativeManaged === true || action.recoveryRequired) requireRecovery(action)
  else action.status = Date.parse(action.expiresAt) <= Date.now() ? 'EXPIRED' : 'FAILED'
}
