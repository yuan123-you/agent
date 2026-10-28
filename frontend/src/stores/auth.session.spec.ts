import {beforeEach,describe,expect,it,vi} from 'vitest'
import {createPinia,setActivePinia} from 'pinia'
import {useAuthStore} from './auth'
const mocks=vi.hoisted(()=>({logout:vi.fn()}))
vi.mock('@/api',()=>({apiLogin:vi.fn(),apiLogout:mocks.logout,apiMe:vi.fn(),apiRegister:vi.fn(),apiRegisterCustomer:vi.fn(),apiRegisterMerchant:vi.fn()}))
const account=(id:number)=>({accessToken:'access-'+id,refreshToken:'refresh-'+id,user:{userId:id,username:'user'+id,nickname:'User '+id,role:'CUSTOMER' as const}})
beforeEach(()=>{vi.clearAllMocks();localStorage.clear();setActivePinia(createPinia())})
describe('authentication state recovery',()=>{
 it.each(['not-json','7','[]','{"userId":1,"role":"CUSTOMER","nickname":5}','{"userId":1,"username":"one","nickname":"One","role":"UNKNOWN"}'])('recovers invalid cached user %s without crashing or trapping a stale token',value=>{
  localStorage.setItem('token','stale-access');localStorage.setItem('refreshToken','stale-refresh');localStorage.setItem('user',value)
  let auth!:ReturnType<typeof useAuthStore>;expect(()=>{auth=useAuthStore()}).not.toThrow();expect(auth.isLoggedIn).toBe(false);expect(auth.user).toBeNull();expect(localStorage.getItem('token')).toBeNull()
 })
 it('retains a valid cached account',()=>{const data=account(1);localStorage.setItem('token',data.accessToken);localStorage.setItem('refreshToken',data.refreshToken);localStorage.setItem('user',JSON.stringify(data.user));expect(useAuthStore().user).toEqual(data.user);expect(useAuthStore().isLoggedIn).toBe(true)})
 it.each(['success','failure'])('does not clear a newer login when an older logout finishes with %s',async outcome=>{
  let resolve!:()=>void,reject!:(error:Error)=>void;mocks.logout.mockReturnValue(new Promise<void>((yes,no)=>{resolve=yes;reject=no}))
  const auth=useAuthStore();auth.setAuth(account(1));const pending=auth.logout();auth.setAuth(account(2));if(outcome==='success')resolve();else reject(new Error('offline'));await pending
  expect(auth.user?.userId).toBe(2);expect(auth.token).toBe('access-2');expect(localStorage.getItem('refreshToken')).toBe('refresh-2')
 })
 it('still logs out the same refresh-token session after a peer access-token refresh',async()=>{
  let resolve!:()=>void;mocks.logout.mockReturnValue(new Promise<void>(yes=>resolve=yes));const auth=useAuthStore();auth.setAuth(account(1));const pending=auth.logout();localStorage.setItem('token','peer-access');resolve();await pending;expect(auth.isLoggedIn).toBe(false);expect(localStorage.getItem('refreshToken')).toBeNull()
 })
})
