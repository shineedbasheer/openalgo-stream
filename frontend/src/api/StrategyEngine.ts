import axios from 'axios'

/**
 * Dedicated axios client for the Strategy Engine (ESB) service.
 * Requests to /esb/* are proxied server-side:
 *   - Dev (Vite): via vite.config.ts proxy
 *   - Prod (Flask): via Flask esb_proxy blueprint
 */
const esbClient = axios.create({
  headers: {
    'Content-Type': 'application/json',
  },
})

// Response interceptor for error handling
esbClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      console.error(
        `[StrategyEngine] API error: ${error.response.status}`,
        error.response.data
      )
    } else if (error.request) {
      console.error('[StrategyEngine] No response received:', error.message)
    } else {
      console.error('[StrategyEngine] Request setup error:', error.message)
    }
    return Promise.reject(error)
  }
)

/**
 * Strategy parameters - dynamic key-value pairs specific to each strategy
 */
export interface StrategyParameters {
  [key: string]: number
}

/**
 * A registered strategy from the ESB service
 */
export interface RegisteredStrategy {
  exchange: string
  filterSymbols: string[]
  gateway: string
  indicators: string[]
  maxReplaceCount: number
  positionType: string
  replaceIntervalSeconds: number
  strategyId: string
  strategyName: string
  strategyParameters: StrategyParameters
  timeInForce: string
  userId: string
}

/**
 * Generic action response from ESB (stop, exit, etc.)
 */
export interface StrategyActionResponse {
  apiVersion: string
  failure: boolean
  status: string
  success: boolean
  message?: string
  errorMessage?: string
  strategyId?: string
}

/**
 * Response shape for the single strategy config endpoint
 */
export interface StrategyConfigResponse {
  apiVersion: string
  failure: boolean
  status: string
  success: boolean
  config: RegisteredStrategy
}

/**
 * Strategy Engine API - calls the external ESB service
 */
export const strategyEngineApi = {
  /**
   * Get registered strategies for a user
   */
  getRegisteredStrategies: async (userId: number): Promise<RegisteredStrategy[]> => {
    const response = await esbClient.get<RegisteredStrategy[]>(
      `/esb/api/strategies/user/${userId}/registered`
    )
    return response.data
  },

  /**
   * Get full strategy configuration (including strategyParameters) by strategyId
   */
  getStrategyConfig: async (strategyId: string): Promise<RegisteredStrategy> => {
    const response = await esbClient.get<StrategyConfigResponse>(
      `/esb/api/strategies/strategy/${strategyId}/registered`
    )
    return response.data.config
  },

  /**
   * STOP single strategy
   */
  stopStrategy: async (strategyId: number): Promise<StrategyActionResponse> => {
    const response = await esbClient.post<StrategyActionResponse>(
      `/esb/api/strategies/${strategyId}/stop`
    )
    return response.data
  },

  /**
   * STOP all strategies for a user
   */
  stopAllStrategies: async (userId: number): Promise<StrategyActionResponse> => {
    const response = await esbClient.post<StrategyActionResponse>(
      `/esb/api/strategies/user/${userId}/stop-all`
    )
    return response.data
  },

  /**
   * EXIT all positions for a single strategy
   */
  exitAllPositions: async (strategyId: number): Promise<StrategyActionResponse> => {
    const response = await esbClient.post<StrategyActionResponse>(
      `/esb/api/strategies/${strategyId}/exit-all`
    )
    return response.data
  },

  /**
   * EXIT all positions for ALL strategies
   */
  exitAllPositionsForAllStrategies: async (): Promise<StrategyActionResponse> => {
    const response = await esbClient.post<StrategyActionResponse>(
      `/esb/api/strategies/exit-all-positions`
    )
    return response.data
  },

}
