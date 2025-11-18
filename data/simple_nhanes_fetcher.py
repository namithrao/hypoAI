"""
Simple NHANES Variable Fetcher
Directly fetches variable lists from CDC website without external dependencies.
"""

import pandas as pd
import time


class SimpleNHANESFetcher:
    """
    Simplified NHANES variable fetcher that makes direct HTTP requests to CDC.
    Emulates the nhanes_data API functionality.
    """

    def __init__(self):
        self.base_url = "https://wwwn.cdc.gov/nchs/nhanes/search/variablelist.aspx"
        self.cycle_list = [
            '1999-2000', '2001-2002', '2003-2004', '2005-2006', '2007-2008',
            '2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'
        ]

    def fetch_variables(self, cycle, component):
        """
        Fetch variables for a specific cycle and component.

        Args:
            cycle: Year cycle (e.g., "2017-2018")
            component: Data category (e.g., "Laboratory")

        Returns:
            pd.DataFrame with columns: Variable Name, Variable Description,
                                        Data File Name, Data File Description, Component
        """
        # Parse cycle
        begin_year, end_year = cycle.split('-')

        # Build URL
        url = f"{self.base_url}?Component={component.capitalize()}&BeginYear={begin_year}&EndYear={end_year}"

        print(f"   Fetching {component} from CDC website...")

        try:
            # Read HTML table directly from CDC website
            tables = pd.read_html(url)

            if not tables:
                print(f"   ⚠️  No tables found for {component}")
                return pd.DataFrame()

            # First table contains variable list
            df = tables[0]

            # Clean up column names
            df.columns = df.columns.str.strip()

            # Add component column
            df['Component'] = component.capitalize()

            # Filter to only this cycle
            if 'Begin Year' in df.columns and 'EndYear' in df.columns:
                df = df[
                    (df['Begin Year'].astype(str) == begin_year) &
                    (df['EndYear'].astype(str) == end_year)
                ]

            print(f"   ✅ Found {len(df)} variables for {component}")

            return df

        except Exception as e:
            print(f"   ❌ Error fetching {component}: {e}")
            return pd.DataFrame()

    def fetch_all_for_cycle(self, cycle):
        """
        Fetch all variables for all components in a cycle.

        Args:
            cycle: Year cycle (e.g., "2017-2018")

        Returns:
            pd.DataFrame with all variables
        """
        components = ['Demographics', 'Dietary', 'Examination', 'Laboratory', 'Questionnaire']

        all_variables = []

        print(f"\n🔍 Fetching all NHANES {cycle} variables...\n")

        for component in components:
            df = self.fetch_variables(cycle, component)
            if not df.empty:
                all_variables.append(df)
            time.sleep(0.5)  # Be nice to CDC servers

        if all_variables:
            combined = pd.concat(all_variables, ignore_index=True)

            # Standardize column names
            column_mapping = {
                'Variable Name': 'variable_name',
                'Variable Description': 'variable_description',
                'Data File Name': 'data_file_name',
                'Data File Description': 'data_file_description',
                'Component': 'component'
            }

            # Only rename columns that exist
            rename_dict = {k: v for k, v in column_mapping.items() if k in combined.columns}
            combined = combined.rename(columns=rename_dict)

            print(f"\n✅ Total variables fetched: {len(combined)}")
            print(f"\nVariables per component:")
            if 'component' in combined.columns:
                print(combined['component'].value_counts())

            return combined
        else:
            return pd.DataFrame()


# Test the fetcher
if __name__ == "__main__":
    fetcher = SimpleNHANESFetcher()

    # Fetch all 2017-2018 variables
    df = fetcher.fetch_all_for_cycle("2017-2018")

    if not df.empty:
        print(f"\n📊 Sample data:")
        print(df.head(10))

        # Save to CSV
        df.to_csv('nhanes_2017_2018_variables.csv', index=False)
        print(f"\n💾 Saved to nhanes_2017_2018_variables.csv")
