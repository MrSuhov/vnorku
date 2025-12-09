import HeroSection from '@/components/home/HeroSection';
import MealPlanDemoSection from '@/components/home/MealPlanDemoSection';
import ProblemSection from '@/components/home/ProblemSection';
import SolutionSection from '@/components/home/SolutionSection';
import HowItWorksSection from '@/components/home/HowItWorksSection';
import BenefitsSection from '@/components/home/BenefitsSection';
import FAQSection from '@/components/home/FAQSection';
import CTASection from '@/components/home/CTASection';

export default function HomePage() {
  return (
    <>
      <HeroSection />
      <MealPlanDemoSection />
      <ProblemSection />
      <SolutionSection />
      <HowItWorksSection />
      <BenefitsSection />
      <FAQSection />
      <CTASection />
    </>
  );
}
