Here is what I'm building:

This is a realtime system that uses Swift 6 programming language. When I start this is should create an invironment of that facilirtates Kernels to send messages to each other as a result of their comutation. The connection between different kernels is externally defined by a configuration. There are several types of Kernels:

1. Sensing Kernels - these are the kernels that will receive information from the OS. For example one of the sensing kernels can receive audio frames from a microphone. 

2. Expression Kernels - these are the output kernels that will update UI, produce sounds and so on.

3. Memory Kernels - these are kernels that can store information and that other kernels can query infomration from. It can contain long-term memories in the database or can contain working memory in actual RAM

4. Motor Kernels - produce commands for expression kernels to create the expressions. They're also responsible for attention. It communicates with sensing kernels to highlight what information is important 

5. Learning Kernels - responsible for updating memory and learning. 

6. Executive Kernels - these are where application logic exists. For example it can get information from sensing kernel, and decide to update memory kernal with new information or tell Motor kernel to ask expression kernel to produce certain output.

For the UI (since this is an app that runs in terminal for now), we can use SwiftTUI https://github.com/rensbreur/SwiftTUI.git

First thing that I want to do is implement a common Kernel protocol. Each kernel should be a distributed actor so that the system can be executed on multiple computers if neccessary. But for first implementation we'll run everything local one machine (syste: system)

There has to be an active system that works like this:

The microphone is actively listening using MacOS built in Swift libraries. When I say something - this gets piped into a Sensing Kernel that is responsible for speach recognition. It turns it into text (also using Apple's frameworks for now). After that it sends this into planning kernel. Planning kernel (for now) sends this data to motor, which sends it to expression kernel, which just prints this text in the console. This is the minimal project. We're focusing on architecture, and organization and robustness. The even loop and messaging is very important to get right. I'm not sure messaging bus is ideal, I don't want every kernel (because there will be many of these) to read every message if they're not addressed to them. We can probably just explicitly state connections. 

This whole framework is like an OS that will be running application that are described with kernels and login inside the kernels.

What I want in the end is the following:

I have a folder "example-app" that has app.swift in there. When I run something like "os run example-app" it will go into that folder and load app.swift, which will contain a class ExampleApp that is derived from generic App class. It will implement init and run functions. Init will ask OS to allocate Sensing Kernel and Motor Kernel and so on. It will pass custom function (logic into Executive Kernel). While creating Sensing Kernel, it can specify modality (speech to text). Then it will ask the OS to connect the kernels in a specific way. Sensing to Executive. Then Executive to Motor. Then Motor to Expression. The OS will provide realtime environment to run this. When the app is executed, I expect the microphon to come on and then have Sensing module convert voice to text then send the message down the line just as I specified in init function. Not all kernels require custom function that they execute provided by the app. There is default behavior. I.e. Sensing (based on settings) just does voice to text and sends it. Executive Kernel doesn't do anything by default, that why we need to provide it with a function of how to process messages and where to direct new messages. 