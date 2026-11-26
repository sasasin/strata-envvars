# `DF2B_VARIANT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

`DF2B_VARIANT` は、macOS/Metal の独立ベンチマーク `df2_bench` が使う DFlash2 行列カーネルの `R_S` variant を選ぶ。通常の Strata engine やモデル推論の設定として読まれる箇所はなく、このベンチマーク内の CPU 比較と計測用 dispatch にだけ使われる。Q4_0 カーネルの CPU 比較に加え、head が通常経路なら Q8_0 head の dispatch にも同じ variant 文字列を渡す（`engine/metal/tests/df2_bench.cpp:1-9,120-127,135-164,405-406`）。Metal CMake は `tests/*.cpp` を個別実行ファイルとして生成し、Metal ビルド自体を Apple に限定する（`engine/metal/CMakeLists.txt:18-20,43-55`）。

## 値と判定

`main` で `std::getenv` が null なら文字列 `4_8` を使い、設定されていれば値をそのまま `std::string` にする。空文字も「設定済み」となり、既定値には戻らない（`engine/metal/tests/df2_bench.cpp:62-82`）。その後 `std::sscanf(s.c_str(), "%d_%d", &R, &S)` で整数 2 個を読み取るが、戻り値は確認せず、末尾まで消費したか・値域が妥当かの検証もない（同 `:80-82`）。

通常経路では起動時の Q4_0 比較が先に実行されるため、実際に選択できる文字列は Metal kernel が公開する関数名 `df2_mm4_R_S` に一致する次の 10 個。`R` と `S` の組み合わせはカーネル側の明示的な template 展開で限定される（`engine/metal/src/engine/msl/dflash2.metal:555-556`）。Q8_0 用の `df2_mm_R_S` には追加で `1_16` も定義されているが、通常経路では先行する Q4_0 比較で対応関数が見つからず終了するため、その値だけを `DF2B_VARIANT` に設定して head 計測へ進むことはできない（同 `:485-486`; `engine/metal/tests/df2_bench.cpp:135-144,405-406`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `DF2B_KIND` が `mma` / `frag` 以外（通常の Q4_0 bench path） | `4_8` | `1_4`, `1_8`, `2_4`, `2_8`, `2_16`, `4_4`, `4_8`, `4_16`, `8_4`, `8_8` | 空文字、`4_9`、`4_8x`、`4_8 ` など、kernel 名と一致しない値 |
| `DF2B_KIND=mma` または `DF2B_KIND=frag` | `4_8` の文字列は取得されるが variant 選択には使われない | 該当なし | variant 選択には使われない（`DF2B_KIND` による分岐は `engine/metal/tests/df2_bench.cpp:67-72,136-137,285-318`） |

文字列比較・関数名生成には元の文字列全体が使われるため、大文字小文字を変えたり空白を足したりした値は一致しない。`sscanf` 自体は先頭から `%d_%d` を読み、後続文字を検査しないものの、例えば `4_8x` はパイプライン名も `df2_mm4_4_8x` となり、要求された関数がなければ失敗する（`engine/metal/tests/df2_bench.cpp:80-82,141-144`; `engine/metal/src/engine/msl/dflash2.metal:555-556`; `engine/metal/src/mtl_rt.mm:229-255`）。不正値に対して `sscanf` の失敗を処理するコードはなく、`R` / `S` が未初期化のまま参照される経路もあるため、未対応値の挙動を一律に断定できない（`engine/metal/tests/df2_bench.cpp:80-82,141-144,285-324`）。

## 有効になる条件

- 対象は Apple の Metal ビルドで生成される `df2_bench`。Metal CMake は Apple 以外を拒否し、`tests/*.cpp` からベンチマークを独立 executable として作る（`engine/metal/CMakeLists.txt:18-20,43-55`）。
- `DF2B_KIND` が `mma` または `frag` なら、それぞれ native MMA / fragment path となり、初期の通常 Q4_0 比較は飛ばされ、`mm` lambda も `m.native` / `m.frag` 分岐で別 kernel 名を使うため `DF2B_VARIANT` は kernel 選択に使われない（`engine/metal/tests/df2_bench.cpp:67-72,136-137,285-318`）。
- 通常 path では、読み取った文字列に対応する `df2_mm4_<値>` kernel がコンパイル済みライブラリに存在する必要がある。見つからない場合、`Context::pipeline` は `mtl: no function <名前> <詳細>` を stderr に出して終了コード 3 で終了する（`engine/metal/tests/df2_bench.cpp:66,141-144`; `engine/metal/src/mtl_rt.mm:229-255`）。
- CLI 引数による variant 上書きはない。`argv[1]` は kernel directory にだけ渡される（`engine/metal/tests/df2_bench.cpp:62-66`）。
- `DF2B_SKIP=mm` では通常の `mm` lambda 内の dispatch が省略されるが、その前段にある `!NATIVE && !FRAG` の CPU 比較用 dispatch は別に実行されるため、そこで variant が使われる（`engine/metal/tests/df2_bench.cpp:135-144,285-288`）。`DF2B_ONLY` は計測ステージを限定するが、variant 自体を上書きしない（同 `:452-464`）。

## 実行時の詳細

環境値は `main` の開始時にローカル文字列 `var` として一度取得され、同関数内で比較用・計測用 dispatch の組み立てに再利用される。環境を読み直す関数やキャッシュ更新処理はない（`engine/metal/tests/df2_bench.cpp:62-82,285-324`）。通常 path では `var` が Q4_0 用 `df2_mm4_<var>` のパイプライン名を作り、`sscanf` で得た `R` と `S` が threadgroup grid / threadgroup size の計算に使われる。head の通常経路では同じ `var` から Q8_0 用 `df2_mm_<var>` を選ぶ（同 `:80-82,135-144,285-324,405-406`）。`var` は context update、block、head、FULL ROUND などで組み立てる計測 dispatch に渡される（同 `:342-389,405-415,452-464`）。このプログラムはベンチ用のランダムデータを作り、選択結果を推論 token として返す実行経路ではない（同 `:96-132,260-283`）。

## ログと測定値

起動後に device 名を stdout に出し、通常は variant を含む設定行 `config: pos ..., mm4 variant ..., head variant ..., host gap ... ms, iters ...` を表示する（`engine/metal/tests/df2_bench.cpp:62-65,441`）。通常 Q4_0 path は先に `df2_mm4_<var> check: max |gpu - cpu| ...` を出し、誤差条件に失敗すると終了コード 1 を返す（同 `:135-164`）。計測行は GPU 時間および encode+submit+wait の median / p10 / p90 を stdout に出す（同 `:426-439`）。この調査ではベンチマークを実行しておらず、測定値は記載しない。

## 根拠

- 読み取り、既定値、文字列 parse: `engine/metal/tests/df2_bench.cpp:62-82`
- 通常 path の kernel 選択と dispatch geometry: `engine/metal/tests/df2_bench.cpp:135-164,285-324`
- 選択可能な Metal kernel 名: `engine/metal/src/engine/msl/dflash2.metal:485-486,555-556`
- 未解決 kernel の stderr と終了: `engine/metal/src/mtl_rt.mm:229-255`
- Apple 限定と benchmark executable の生成: `engine/metal/CMakeLists.txt:18-20,43-55`
