<script setup>
    import { RouterLink } from 'vue-router';
</script>

<template>
    <div class="main-div">
        <div class="child1">Eventyay</div>
    </div>
    <div class="submain-div">        
        <RouterLink to="/schedule" >        
            Schedule
        </RouterLink>
        <RouterLink to="/schedule-editor">
            Schedule-Editor
        </RouterLink>
        <RouterLink to="/videos">
            Videos
        </RouterLink>
        <RouterLink to="/web-checkin">
            Web-Checkin
        </RouterLink>             
    </div>
</template>


<style scoped>
.main-div{
    margin: 30px;
    justify-items: center;
    align-items: center;  
}

.child1{
    padding: 15px;
    color: white;
    background-color: rgba(23,75,118,0.9);
    border-radius: 10px;
    border: solid 1px transparent;
    font-size:xx-large;
}
.submain-div{
    display: flex;
    justify-content:space-evenly;
    margin: 60px 50px ;
}
a{     
    background-color: rgba(33,133,208, 0.2);
    color:rgb(33,133,208);
    border-radius: 10px;
    font-size:larger;
    padding: 10px;
    border: solid 1px transparent;
    text-decoration: none;
    transition: background-color 0.3s ease;
}

a:hover {
  background-color: rgba(33,133,208, 0.4); 
}

</style>