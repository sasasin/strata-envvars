# `ALLOW_BAD_OCLOC`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

SYCL ビルドスクリプト `engine/sycl/tools/build.sh` の `ocloc` 既知不具合に対する事前チェックを迂回するビルド時環境変数である。対応する条件下で、既知の `ocloc` が検出されてもスクリプトを終了させず、CMake/Ninja のビルドへ進ませる。実行時の Strata engine の設定ではない（`engine/sycl/tools/build.sh:25-36,38-46`）。

## 値と判定

スクリプト実行時、Bash の `${ALLOW_BAD_OCLOC:-}` を文字列 `1` と完全一致で比較する。未設定と空文字はどちらも空文字として扱われ、`1` 以外なら迂回しない。数値変換や trim、大文字小文字変換は行わない（`engine/sycl/tools/build.sh:25`）。

| ビルド条件 | unset / 空文字 | 迂回する値 | 迂回しない値 |
|---|---|---|---|
| `AOT` が `bmg` または `lnl` で始まり、`I8_ESIMD` が `OFF` ではない場合 | チェックを実行 | `1` | `0`, `true`, `01`, `1 `, `TRUE` など |
| 上記以外 | この変数による差はない | `1` を指定しても判定対象外 | 同左 |

## 有効になる条件

- ビルド時に `engine/sycl/tools/build.sh` を実行すること。文書に示された利用経路は `strata-sycl-dev` コンテナ内からの実行である（`docs/INTEL.md:68-79`）。
- 既知不具合の事前チェック自体は、現在の `AOT` が `bmg` または `lnl` で始まり、かつ `I8_ESIMD` が大文字小文字を含め厳密に `OFF` ではない場合に限り評価される。`AOT` 未設定なら対象外。`I8_ESIMD=off` などは `OFF` と同じ扱いにならず、チェック対象になる（`engine/sycl/tools/build.sh:25`）。
- 条件を満たしても、`ocloc` のバージョン取得に失敗する、バージョン文字列が空、または `26.22.38646` / `26.22.38646.*` と一致しない場合、既知不具合の停止分岐には入らない。バージョン取得は PATH 上の `ocloc --version` の出力から最初の `数字.数字.数字` または `数字.数字.数字.数字` を抽出する（`engine/sycl/tools/build.sh:15-24,26-27`）。
- `ALLOW_BAD_OCLOC=1` は `AOT` や CMake のキャッシュ値を変更せず、チェック分岐だけを飛ばす。既存 build directory のキャッシュについては `build.sh` が「AOT などは既存設定のまま」としている（`engine/sycl/tools/build.sh:38-43`）。スクリプトは毎回、CMake/Ninja より前に現在の環境値でガードを評価する。

## 実行時の詳細

`build.sh` の起動直後、oneAPI の `setvars.sh` を source した後に環境を一度評価する。関数内 static cache やリクエスト単位の読み直しはなく、スクリプト実行中の環境変更を反映するコードもない（`engine/sycl/tools/build.sh:7-8,25-36`）。この名前を CMake の `-D` 引数に渡す処理はなく、engine 起動時に読む実装も見つからない（`engine/sycl/tools/build.sh:38-46`）。

既知のバージョンに該当し、`ALLOW_BAD_OCLOC` が厳密に `1` でなければ、スクリプトは stderr に診断と回避案を出して `exit 2` するため、CMake/Ninja のビルドへ進まない。`1` ならこの事前終了だけが抑止され、通常の configure/build が続く。後続のビルドが成功する保証はコードにない。実際の `cmake --build` が失敗すれば、スクリプトはその終了コードを返す（`engine/sycl/tools/build.sh:28-35,44-52`）。

## ログと測定値

ガードが発火した場合の stderr は次の内容（`$v` と `$AOT` は実行時値）で、終了コードは `2`。このメッセージは修正方法として `docker build --pull`、`I8_ESIMD=OFF`、`ALLOW_BAD_OCLOC=1` を案内する（`engine/sycl/tools/build.sh:28-35`）。

```text
build.sh: this image's ocloc is $v (IGC 2.36.3). It is known to crash while it compiles the int8 ESIMD kernels for AOT=$AOT (#3219).
  Fix: rebuild the image with a fresh base, then build again:   docker build --pull -t strata-sycl-dev engine/sycl/tools
  Or build without those kernels (the prompt's experts take the slower XMX path):   I8_ESIMD=OFF
  Or build anyway:   ALLOW_BAD_OCLOC=1
```

`ALLOW_BAD_OCLOC=1` でチェックを迂回した場合、この事前警告は出ない。ソースコメントは特定バージョンでのコンパイラ異常終了を説明するが、この調査ではビルドや GPU 実行による再現確認をしていない（`engine/sycl/tools/build.sh:10-14,25-35`）。この変数について Strata 資料に測定値はない。

## 根拠

- 読み取り条件、バージョン照合、警告、事前終了: `engine/sycl/tools/build.sh:10-36`
- CMake / build の後続処理と終了コード: `engine/sycl/tools/build.sh:38-52`
- 文書化されたコンテナ内の呼び出し経路: `docs/INTEL.md:60-89`
