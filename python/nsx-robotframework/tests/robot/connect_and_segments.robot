*** Settings ***
Library    NSXLibrary
Library    FakeNSX    WITH NAME    Fake
Suite Setup     Start Fake NSX
Suite Teardown  Stop Fake NSX
Test Setup      Connect To NSX    ${NSX_URL}    admin    pass    verify=${FALSE}
Test Teardown   Disconnect From NSX

*** Variables ***
${NSX_URL}      ${EMPTY}
${WEB_SEG}      /infra/segments/web

*** Test Cases ***
List And Get Segments
    ${segments}=    NSX List Segments
    Length Should Be    ${segments}    2
    ${web}=    NSX Get Segment    web
    Should Be Equal    ${web}[id]    web

Create Segment Sends Correct Resource Type
    ${body}=    Create Dictionary    display_name=web
    ${result}=    NSX Create Segment    web    ${body}
    Should Be Equal    ${result}[resource_type]    Segment

Segment Contains Expected VM
    NSX Segment Should Contain VM    web    vm-123

Segment Does Not Contain Unknown VM
    Run Keyword And Expect Error    *vm-999*    NSX Segment Should Contain VM    web    vm-999

Segment Realizes Within Timeout
    NSX Wait For Realization    ${WEB_SEG}    timeout=5
    NSX Should Be Realized    ${WEB_SEG}    timeout=5

Tier-1 Gateway Realizes
    NSX Gateway Should Be Realized    1    t1-a    timeout=5

BGP Neighbor Is Established
    NSX BGP Neighbor Should Be Established    lr-1    10.0.0.1

BGP Neighbor Not Established Fails
    Fake NSX Set BGP Neighbor State    10.0.0.1    ACTIVE
    Run Keyword And Expect Error    *ACTIVE*    NSX BGP Neighbor Should Be Established    lr-1    10.0.0.1

LB Virtual Server Listed
    ${vs}=    NSX List LB Virtual Servers
    Should Be Equal    ${vs}[0][id]    vs-1

Generic Verbs Work
    Fake NSX Set BGP Neighbor State    10.0.0.1    ESTABLISHED
    ${seg}=    NSX GET    /infra/segments/web
    Should Be Equal    ${seg}[id]    web
    ${neighbors}=    NSX Manager GET    /logical-routers/lr-1/routing/bgp/neighbors
    Should Be Equal    ${neighbors}[results][0][state]    ESTABLISHED

*** Keywords ***
Start Fake NSX
    ${url}=    Fake.Start Fake NSX
    Set Suite Variable    ${NSX_URL}    ${url}

Stop Fake NSX
    Fake.Stop Fake NSX
