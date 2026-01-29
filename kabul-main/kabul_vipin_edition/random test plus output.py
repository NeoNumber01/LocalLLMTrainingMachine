"""
task1: 

java
public String getProcessName(int id) {
    return "Process_" + id;
}

csharp
public string GetProcessName(int id) 
{
    return "Process_" + id;
}

output
public virtual string GetProcessName(int id){return "Process_" + id;}

-------------------------------------------------------------------------------------------------------------
-------------------------------------------------------------------------------------------------------------
-------------------------------------------------------------------------------------------------------------

task2:

java
public void verifyUser(boolean isValid) {
    if (isValid) {
        System.out.println("Access Granted");
    }
}

csharp
public void VerifyUser(bool isValid) 
{
    if (isValid) {
        Console.WriteLine("Access Granted");
    }
}

output
public void VerifyUser(bool isValid){if (isValid){System.Console.WriteLine("Access Granted");}

-------------------------------------------------------------------------------------------------------------
-------------------------------------------------------------------------------------------------------------
-------------------------------------------------------------------------------------------------------------

task 3:

java
public int listSize(ArrayList<String> list) {
    return list.size();
}

csharp
public int ListSize(List<string> list) 
{
    return list.Count;
}

output
public virtual int ListSize(IList<string> list){return list.Count;}


-------------------------------------------------------------------------------------------------------------
-------------------------------------------------------------------------------------------------------------
-------------------------------------------------------------------------------------------------------------

task 4:

java
public String getDayType(int day) {
    switch (day) {
        case 1: return "Weekend";
        case 2: return "Weekday";
        default: return "Unknown";
    }
}

csahrp
public string GetDayType(int day) 
{
    switch (day) 
    {
        case 1: return "Weekend";
        case 2: return "Weekday";
        default: return "Unknown";
    }
}

output
public virtual string GetDayType(int day){switch (day){case 1: return "Weekend";case 2: return "Weekday";case 3: return "Weekday";case 4: return "Unknown";}

-------------------------------------------------------------------------------------------------------------
-------------------------------------------------------------------------------------------------------------
-------------------------------------------------------------------------------------------------------------

task 5:

java
public class Dog extends Animal {
    private String breed;

    public Dog(String name, String breed) {
        super(name);
        this.breed = breed;
    }

    public void bark() {
        System.out.println("Woof!");
    }
}

csahrp
public class Dog : Animal 
{
    private string breed;

    public Dog(string name, string breed) : base(name) 
    {
        this.breed = breed;
    }

    public void Bark() 
    {
        Console.WriteLine("Woof!");
    }
}

output
public Dog(string name, string breed): base(name){this.breed = breed;}



public Dog(string name, string breed){

base(name);

this.breed = breed;

public void Bark(){

System.Console.WriteLine("Woof!");

}

}

-------------------------------------------------------------------------------------------------------------
-------------------------------------------------------------------------------------------------------------
-------------------------------------------------------------------------------------------------------------

task 6:

java
public void readFile(String path) {
    try {
        System.out.println("Opening: " + path);
    } catch (Exception e) {
        System.out.println("Error: " + e.getMessage());
    } finally {
        System.out.println("Done.");
    }
}

csahrp
public void ReadFile(string path) 
{
    try {
        Console.WriteLine("Opening: " + path);
    } catch (Exception e) {
        Console.WriteLine("Error: " + e.Message);
    } finally {
        Console.WriteLine("Done.");
    }
}

output
public virtual void ReadFile(string path){
 try{
        System.Out.WriteLine("Opening: " + path);
    }catch (Exception e){
        System.Out.WriteLine("Error: " + e.Message);
    }finally{
        System.Out.WriteLine("Done.");}
}





"""