from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    auth=("neo4j", os.getenv("NEO4J_PASSWORD"))
)

def import_rich_sample(tx):
    tx.run("""
    // Person
    MERGE (u:Person {
      userId: 'user_123',
      name: 'Chandan Galani',
      age: 35,
      city: 'Mumbai',
      monthlyIncomeINR: 5000000,
      riskTolerance: 'moderate',
      maritalStatus: 'married',
      dependents: 2
    })

    // Real Estate
    MERGE (house:RealEstate {
      assetId: 're_001',
      name: 'Bandra West Residence',
      address: 'Bandra West, Mumbai',
      pinCode: '400050',
      marketValueINR: 32000000,
      loanOutstandingINR: 18000000,
      emiMonthlyINR: 185000,
      purchaseDate: date('2023-06-15')
    })

    // Equity
    MERGE (eq:Equity {
      assetId: 'eq_001',
      name: 'Large-cap Portfolio',
      currentValueINR: 42000000,
      costBasisINR: 28000000,
      purchaseDate: date('2022-11-10')
    })

    // Startup Equity
    MERGE (startup:StartupEquity {
      assetId: 'se_001',
      companyName: 'Intent Engine Pvt Ltd',
      vestedShares: 12500,
      totalShares: 100000,
      valuationINR: 150000000,
      vestingSchedule: '4 years with 1 year cliff'
    })

    // Liability (home loan)
    MERGE (loan:Liability {
      id: 'lia_001',
      type: 'HomeLoan',
      outstandingAmount: 18000000,
      interestRate: 8.75,
      emiMonthly: 185000,
      lender: 'HDFC Bank'
    })

    // Relationships
    MERGE (u)-[:OWNS {ownershipPct: 1.0, since: date('2023-06-15')}]->(house)
    MERGE (u)-[:OWNS {ownershipPct: 1.0, since: date('2022-11-10')}]->(eq)
    MERGE (u)-[:OWNS {ownershipPct: 0.125, since: date('2021-04-01')}]->(startup)
    MERGE (house)<-[:SECURED_BY]-(loan)
    """)

with driver.session() as session:
    session.execute_write(import_rich_sample)

driver.close()
print("Rich sample financial graph imported successfully.")
