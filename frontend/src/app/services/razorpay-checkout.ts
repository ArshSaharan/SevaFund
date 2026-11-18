/**
 * Razorpay Checkout (https://checkout.razorpay.com/v1/checkout.js) is loaded on demand: warmed up when a fundraiser
 * page opens and awaited when the donor presses Donate.  UPI, cards, netbanking and wallets are all chosen inside it.
 */
const CHECKOUT_SRC = 'https://checkout.razorpay.com/v1/checkout.js';
const LOAD_TIMEOUT_MS = 15_000;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type RazorpayCheckout = new (options: any) => { open(): void; on?(event: string, cb: (r: any) => void): void };

let loader: Promise<RazorpayCheckout> | undefined;

export function loadRazorpayCheckout(): Promise<RazorpayCheckout> {
  if (typeof window === 'undefined') return Promise.reject(new Error('Razorpay Checkout needs a browser'));
  const existing = (window as any).Razorpay as RazorpayCheckout | undefined;
  if (existing) return Promise.resolve(existing);

  loader ??= new Promise<RazorpayCheckout>((resolve, reject) => {
    const script = document.createElement('script');
    const fail = (reason: string) => {
      clearTimeout(timer);
      script.remove();
      loader = undefined;                 // allow a retry on the next attempt
      reject(new Error(reason));
    };
    const timer = setTimeout(() => fail('Timed out loading Razorpay Checkout'), LOAD_TIMEOUT_MS);
    script.src = CHECKOUT_SRC;
    script.async = true;
    script.onload = () => {
      const ctor = (window as any).Razorpay as RazorpayCheckout | undefined;
      if (!ctor) return fail('Razorpay Checkout loaded without a Razorpay constructor');
      clearTimeout(timer);
      resolve(ctor);
    };
    script.onerror = () => fail('Failed to load Razorpay Checkout');
    document.head.appendChild(script);
  });
  return loader;
}
