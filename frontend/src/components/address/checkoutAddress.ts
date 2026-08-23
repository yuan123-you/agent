import type { AddressVO } from '@/types/api'

export function preferredAddress(addresses: AddressVO[]): AddressVO | undefined {
  return addresses.find((address) => address.isDefault) || addresses[0]
}
