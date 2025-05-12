import java.util.Scanner;

public class Main{
    public static void greet() {
        System.out.println("Hello, welcome to my program in Java!");
    }

    
    public static void main(String[] args){
        greet();
        Scanner scanner = new Scanner(System.in);
        System.out.print("Enter three numbers seperated by commas (e.g. 5,2,23): ");
        String number = scanner.nextLine();
        String[] parts = number.split(",");
        int[] numbers = new int[parts.length];
        for (int i = 0; i < parts.length; i++){
            numbers[i] = Integer.parseInt(parts[i]);
        }
        int compare = 0;
        for (int num : numbers) {
            if (num > compare) {
                compare = num;
            }
        }
        
        String prefix = String.format("The largest number out of %d, %d and %d is: %d", numbers[0], numbers[1], numbers[2], compare);
        
        System.out.println(prefix);
        scanner.close();

    }
}