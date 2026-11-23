# `HY4S_MARGINS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`strata-hy4-sycl` の非サーバー CLI で通常の greedy decode を実行するとき、decode step ごとに logits の最大値と 2 番目に大きい値の差を記録し、出力ディレクトリの `margins.txt` に保存する診断用スイッチです。値は token 選択や decode 分岐に使われず、追加で logits 行をホストへコピーして差を計算します（`engine/src/hy4flash/sycl/sy_main.cpp:527-575, 598-601`）。対象ファイルは Linux 向け Hy4-Flash SYCL runner の実装で、SYCL ビルドスクリプトがこの `sy_main.cpp` を実行ファイルに含めます（`engine/src/hy4flash/sycl/sy_main.cpp:1, 79`; `engine/src/hy4flash/sycl/build_hy4_sycl.sh:1-6, 62-68`）。

## 値と判定

`std::getenv("HY4S_MARGINS")` の戻り値をポインターとして真偽判定します。文字列の内容は parse・比較されません。未設定なら記録せず、設定されていれば空文字を含む任意の値で記録します。したがって `0`, `false`, `0anything`, 空白、大文字小文字を変えた値も有効です。数値範囲・境界・無効値はありません（`engine/src/hy4flash/sycl/sy_main.cpp:562`）。

| 条件 | unset | 設定時に有効になる値 | 無効になる値 |
|---|---|---|---|
| SYCL runner の通常 decode 枝 | 判定は偽。margin を収集しない | 空文字を含む、環境に設定されたすべての文字列 | 該当なし。設定値の内容は検査しない |

## 有効になる条件

- `strata-hy4-sycl` の SYCL 実装を使う必要があります。この読み取りは `engine/src/hy4flash/sycl/sy_main.cpp` にあります。CUDA/HIP 実装の `HY4S_MARGINS` 参照は確認できません（`engine/src/hy4flash/sycl/sy_main.cpp:1, 562`; `engine/src/hy4flash/sycl/build_hy4_sycl.sh:62-68`）。
- `--serve` を指定したサーバーモードでは、サーバーへ制御を渡して `main` が戻るため、この収集処理を通りません（`engine/src/hy4flash/sycl/sy_main.cpp:215-248`）。
- 非サーバー実行で `--gen N` が正数である必要があります。通常 decode の枝は `gen > 0` のときだけ選ばれます（`engine/src/hy4flash/sycl/sy_main.cpp:156, 527`）。
- さらに先行する `spec_mode`、`--detcheck`、`--wincheck` の枝に入らない必要があります。`spec_mode` は `--draft dfly2` かつ `gen > 0` で、枝の優先順は speculative decode、detcheck、wincheck、通常 decode です（`engine/src/hy4flash/sycl/sy_main.cpp:279, 379-410, 459, 527`）。
- decode ループ内で EOS token に達した時点でその反復は forward を行わず終了します。そのため収集数は `--gen` の値より少なくなることがあり、最初の decode 反復で EOS なら `margins` は空のままです（`engine/src/hy4flash/sycl/sy_main.cpp:538-545`）。
- `--out DIR` が出力先ディレクトリを決めます。指定がなければ `.` です。margin を1件以上収集したときだけ `DIR/margins.txt` を開き、1行に1値で書きます（`engine/src/hy4flash/sycl/sy_main.cpp:155, 598-601`）。

## 実行時の詳細

環境値を読むのは通常 decode の各反復で、関数内 static cache はありません。値を保持したり、起動時に一度だけ判定したりせず、その都度 `getenv` を呼びます（`engine/src/hy4flash/sycl/sy_main.cpp:538-562`）。このコードは環境値を変更せず、CLI 引数による上書きもありません。

各 step で `forward_chunk` と `head` の後、argmax token を `nx` に取得したうえで、変数が設定されている場合は全 `V` logits をホストへコピーして待ちます。走査では最大値 `b1` と次点 `b2` を更新し、`b1 - b2` を `margins` に追加します。次 token はそれとは別に `argmax_row` で得た `nx` を使うため、この margin 値は生成 token やモデル状態を変更しません（`engine/src/hy4flash/sycl/sy_main.cpp:548-573`）。

通常 decode 終了後、margin の配列が空でなければ `out_dir + "/margins.txt"` を開き、浮動小数点値を改行区切りで書きます。ストリームの open/write 成否を検査するコードはありません（`engine/src/hy4flash/sycl/sy_main.cpp:598-601`）。SYCL 処理中に `sycl::exception` が発生した場合は `SYCL exception: %s` を stderr に出して終了コード 4 になります（`engine/src/hy4flash/sycl/sy_main.cpp:612-615`）。

## ログと測定値

この変数専用のログ出力はありません。margin は stdout/stderr には表示せず、条件を満たす場合に `margins.txt` へ出力します（`engine/src/hy4flash/sycl/sy_main.cpp:562, 598-601`）。追加コピーの性能測定値は Strata の該当資料・実装で確認できないため記載しません。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:1, 79-80` — SYCL runner の実装と main。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248, 279, 379-410, 459, 527-562` — サーバー分岐、decode モードの優先順、通常 decode と変数の判定。
- `engine/src/hy4flash/sycl/sy_main.cpp:548-575, 598-615` — logits の収集、margin の計算・ファイル出力、SYCL 例外経路。
- `engine/src/hy4flash/sycl/build_hy4_sycl.sh:1-6, 62-68` — SYCL 用実行ファイルに `sy_main.cpp` を含めるビルド経路。
