#define ALPHABET_LEN 26 // maximum size 26
int main(void) {
    int i = 0, count[ALPHABET_LEN] = { 0 }; // initialize all its elements to zero
    char c = '\0';
    printf("Please enter a line of text: \n");
    /* Read in letter by letter and update the count array */
    c = getchar();
    while (c != '\n' && c >= 0) {
        if (c <= 'z' && c >= 'a')
            ++count[c - 'a']; 
        if (c <= 'Z' && c >= 'A')
            ++count[c - 'A'];
        c = getchar();
    }
    for (i = 0; i < ALPHABET_LEN; ++i) {
        if (count[i] > 0)
            printf("The letter '%c' appears %d time(s).\n", 'a' + i, count[i]);
    }
    return 0;
}