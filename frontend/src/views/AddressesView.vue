<template>
  <div class="page addresses-page">
    <AddressBook />
  </div>
</template>

<script setup lang="ts">
import AddressBook from '@/components/address/AddressBook.vue'
</script>

<style scoped>
.addresses-page { width: min(760px, calc(100% - 32px)); margin: 16px auto; }
</style>
