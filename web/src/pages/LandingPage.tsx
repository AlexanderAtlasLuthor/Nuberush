import { useNavigate } from 'react-router-dom';
import { Flame, ShieldCheck, Truck, BadgeCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/auth';

// Public landing page rendered at `/` for unauthenticated visitors.
// AppEntry (in router.tsx) sends authenticated users to /app first, so
// this component only renders when the visitor has no session.
//
// Visual language matches AuthScreen: dark background (#0A0A0F),
// orange accent (#FF6B2C), white text, flame logo. Single CTA goes to
// /login. Public sign-up is intentionally absent because the backend
// disables /auth/register; admins create users via POST /auth/users.

const LandingPage = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  const goToSignIn = () => {
    // If somehow rendered while authenticated, route to the app shell
    // instead of bouncing through /login. Defense in depth — AppEntry
    // should have redirected already.
    navigate(isAuthenticated ? '/app' : '/login');
  };

  return (
    <div
      className="fixed inset-0 flex flex-col z-50 safe-top overflow-y-auto"
      style={{ backgroundColor: '#0A0A0F' }}
    >
      <div className="flex-1 flex flex-col px-6 pt-20 pb-10 max-w-md mx-auto w-full">
        <div className="text-center mb-10">
          <div
            className="w-20 h-20 rounded-2xl flex items-center justify-center mx-auto mb-6"
            style={{ backgroundColor: '#FF6B2C' }}
          >
            <Flame className="w-11 h-11 text-white" />
          </div>
          <h1 className="text-4xl font-bold text-white tracking-tight">
            NubeRush
          </h1>
          <p
            className="text-sm mt-3 leading-relaxed"
            style={{ color: '#888' }}
          >
            Premium smoke-shop delivery in South Florida.
            <br />
            Fast, legal, verified.
          </p>
        </div>

        <div className="space-y-3 mb-10">
          <FeatureRow
            icon={<Truck className="w-5 h-5" style={{ color: '#FF6B2C' }} />}
            title="Fast delivery"
            body="From licensed local smoke shops straight to your door."
          />
          <FeatureRow
            icon={
              <BadgeCheck
                className="w-5 h-5"
                style={{ color: '#FF6B2C' }}
              />
            }
            title="Age & ID verified"
            body="Every order checked end-to-end before handoff."
          />
          <FeatureRow
            icon={
              <ShieldCheck
                className="w-5 h-5"
                style={{ color: '#FF6B2C' }}
              />
            }
            title="Compliance first"
            body="Restricted and banned products never reach the cart."
          />
        </div>

        <div className="mt-auto space-y-3">
          <Button
            type="button"
            onClick={goToSignIn}
            className="w-full h-12 text-base font-semibold text-white hover:opacity-90"
            style={{ backgroundColor: '#FF6B2C' }}
          >
            Sign In
          </Button>
          <p className="text-center text-xs" style={{ color: '#666' }}>
            Need an account? Contact your administrator.
          </p>
        </div>
      </div>
    </div>
  );
};

interface FeatureRowProps {
  icon: React.ReactNode;
  title: string;
  body: string;
}

const FeatureRow = ({ icon, title, body }: FeatureRowProps) => (
  <div
    className="flex items-start gap-3 rounded-xl p-4"
    style={{ backgroundColor: '#13131A' }}
  >
    <div
      className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
      style={{ backgroundColor: '#1F1F28' }}
    >
      {icon}
    </div>
    <div className="flex-1 min-w-0">
      <p className="text-sm font-semibold text-white">{title}</p>
      <p className="text-xs mt-0.5 leading-relaxed" style={{ color: '#888' }}>
        {body}
      </p>
    </div>
  </div>
);

export default LandingPage;
