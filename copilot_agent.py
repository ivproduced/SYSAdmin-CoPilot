"""
Copilot Agent Layer
Handles Copilot SDK integration with the tool gateway
"""

import asyncio
from typing import AsyncGenerator, Dict, Any, Optional
from copilot import CopilotClient
from tool_gateway import ToolGateway
from dataclasses import dataclass


class ToolWrapper:
    """Wrapper to make tool definitions compatible with SDK expectations"""
    def __init__(self, name: str, description: str, parameters: Dict[str, Any], gateway, tool_name):
        self.name = name
        self.description = description
        self.parameters = parameters
        self._gateway = gateway
        self._tool_name = tool_name
        
        # Create handler matching SDK's ToolHandler signature: Callable[[ToolInvocation], ToolResult]
        async def _handler(invocation: Dict[str, Any]):
            """
            Handle tool invocation from Copilot SDK
            invocation contains: session_id, tool_call_id, tool_name, arguments
            """
            print(f"[ToolWrapper.handler] {tool_name} invoked:")
            print(f"  session_id: {invocation.get('session_id')}")
            print(f"  tool_call_id: {invocation.get('tool_call_id')}")
            print(f"  arguments: {invocation.get('arguments')}")
            
            try:
                # Extract arguments and create context
                params = invocation.get("arguments", {})
                context = {
                    "session_id": invocation.get("session_id"),
                    "tool_call_id": invocation.get("tool_call_id")
                }
                
                # Execute through gateway
                result = await gateway.execute_tool(tool_name, params, context)
                print(f"[ToolWrapper.handler] {tool_name} succeeded: {str(result)[:200]}")
                
                # Return in SDK's expected format
                return {
                    "textResultForLlm": str(result),
                    "resultType": "text"
                }
            except Exception as e:
                error_msg = f"Tool {tool_name} error: {str(e)}"
                print(f"[ToolWrapper.handler] ERROR: {error_msg}")
                import traceback
                traceback.print_exc()
                
                return {
                    "error": error_msg,
                    "resultType": "error"
                }
        
        # Assign handler as a direct attribute
        self.handler = _handler


@dataclass
class AgentResponse:
    """Response from agent"""
    type: str  # "message", "tool_call", "tool_result", "complete", "error"
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[str] = None
    error: Optional[str] = None


class CopilotAgent:
    """
    Copilot Agent - The brain of the system
    
    Responsibilities:
    - Manage Copilot SDK client and session
    - Route tool calls through the gateway
    - Stream responses to interface layer
    - Handle multi-step workflows
    """
    
    def __init__(self, tool_gateway: ToolGateway):
        self.tool_gateway = tool_gateway
        self.client: Optional[CopilotClient] = None
        self.session = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize Copilot SDK"""
        if self._initialized:
            return
        
        print("[CopilotAgent] Initializing...")
        
        # Start Copilot client
        self.client = CopilotClient()
        await self.client.start()
        
        # Get tool definitions from gateway
        tool_defs = self.tool_gateway.get_tool_definitions()
        
        # Wrap tools in format SDK expects
        tools = []
        for tool_def in tool_defs:
            # SDK expects objects with .name, .description, .parameters, .handler attributes
            wrapped = ToolWrapper(
                name=tool_def.name,
                description=tool_def.description,
                parameters=tool_def.input_schema,
                gateway=self.tool_gateway,
                tool_name=tool_def.name
            )
            tools.append(wrapped)
            print(f"[CopilotAgent] Wrapped tool: {tool_def.name}")
        
        self.session = await self.client.create_session({
            "tools": tools,
            "disable_default_tools": True  # Only use our gateway-controlled tools
        })
        
        self._initialized = True
        print(f"[CopilotAgent] Initialized with {len(tools)} tools (default tools disabled)")
    
    async def process_message(self, message: str) -> AsyncGenerator[AgentResponse, None]:
        """
        Process a user message and stream responses
        
        This is the main entry point for agent interactions
        """
        if not self._initialized:
            await self.initialize()
        
        print(f"[CopilotAgent] Processing message: {message}")
        
        # Session recovery: check if session exists, recreate if needed
        if self.session is None:
            print("[CopilotAgent] Session is None, reinitializing...")
            self._initialized = False
            await self.initialize()
        
        try:
            # Set up event tracking
            responses = []
            tool_calls = []
            idle_event = asyncio.Event()
            
            def event_handler(event):
                event_type = event.type.value
                print(f"[CopilotAgent] Event: {event_type}")
                
                # Assistant message
                if event_type == "assistant.message":
                    content = event.data.content if hasattr(event.data, 'content') else None
                    print(f"[CopilotAgent] Message data: {event.data}")
                    print(f"[CopilotAgent] Message content: {content}")
                    if content:
                        responses.append(content)
                        print(f"[CopilotAgent] Added to responses")
                
                # Streaming message delta
                elif event_type == "assistant.message_delta":
                    if event.data.delta_content:
                        if not responses:
                            responses.append("")
                        responses[0] += event.data.delta_content
                
                # Session idle (response complete)
                elif event_type == "session.idle":
                    print(f"[CopilotAgent] Session idle, responses: {len(responses)}")
                    idle_event.set()
            
            # Register event handler
            self.session.on(event_handler)
            
            # Send message to Copilot
            print(f"[CopilotAgent] Sending to Copilot...")
            await self.session.send({"prompt": message})
            
            # Wait for session to become idle (max 60 seconds)
            try:
                await asyncio.wait_for(idle_event.wait(), timeout=60)
            except asyncio.TimeoutError:
                yield AgentResponse(
                    type="error",
                    error="Request timed out after 60 seconds"
                )
                return
            
            # Yield the response
            # Combine all non-empty responses
            full_response = "\n\n".join(r for r in responses if r and r.strip())
            
            if full_response:
                print(f"[CopilotAgent] Yielding response: {full_response[:100]}")
                yield AgentResponse(
                    type="complete",
                    content=full_response
                )
            else:
                print(f"[CopilotAgent] No response received, responses list: {responses}")
                yield AgentResponse(
                    type="error",
                    error="No response received from agent"
                )
        
        except Exception as e:
            error_msg = str(e)
            print(f"[CopilotAgent] Error: {error_msg}")
            
            # If session error, try to recover
            if "Session not found" in error_msg or "session.send failed" in error_msg:
                print("[CopilotAgent] Session error detected, attempting recovery...")
                self._initialized = False
                self.session = None
                
                try:
                    await self.initialize()
                    print("[CopilotAgent] Session recovered, retrying message...")
                    # Retry the message once after recovery
                    async for response in self.process_message(message):
                        yield response
                    return
                except Exception as recovery_error:
                    yield AgentResponse(
                        type="error",
                        error=f"Failed to recover session: {str(recovery_error)}"
                    )
                    return
            
            yield AgentResponse(
                type="error",
                error=f"Agent error: {error_msg}"
            )
    
    async def cleanup(self):
        """Clean up resources"""
        try:
            if self.session:
                await self.session.destroy()
            if self.client:
                await self.client.stop()
        except:
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics"""
        return {
            "initialized": self._initialized,
            "gateway_stats": self.tool_gateway.get_stats()
        }
