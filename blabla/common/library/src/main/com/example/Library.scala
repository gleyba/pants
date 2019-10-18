package com.example

import org.apache.commons.math3.random._

class Library(arg: String) {
  val random = RandomGeneratorFactory.createRandomGenerator(new java.util.Random()).nextLong()
  val messageHuiPizda = s"Using arg: $arg and random double: $random"
}
object Library {
  def apply(arg:String): Library = new Library(arg)
}

object Test {
  def init(): Unit = {
    // commenting out this line results in linking success
    val random = RandomGeneratorFactory.createRandomGenerator(new java.util.Random()).nextLong()
    println(s"Hello Bazel: $random")
  }
}