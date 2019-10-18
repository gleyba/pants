package com.example

import com.example._

object App {
  def main(args: Array[String]): Unit = {
    args.foreach(arg => println(Library(arg).messageHuiPizda))
  }
}