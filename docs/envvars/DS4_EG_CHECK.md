# `DS4_EG_CHECK`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1（DS4）の Engram reader が、unbuffered I/O で読み込んだ行を buffered I/O でも読み直し、両方のバイト列が一致するか数える診断スイッチです。実際の行データとして使われるのは引き続き unbuffered 側の結果です。不一致を見つけても、その行を buffered 側のデータに置き換えたり、処理を中止したりはしません。

## 値と判定

| 状態 | 判定 |
|---|---|
| 未設定 | 比較しない |
| 設定あり（空文字を含む） | 比較する |

値の内容は parse されず、`std::getenv("DS4_EG_CHECK") != nullptr` だけで判定します。したがって `0`、`false`、空文字でも有効です。

判定結果は unbuffered read 成功後に評価される関数内 `static const bool` に保存されます。プロセス内で最初にその箇所へ到達した後に環境を変更しても、この判定は変わりません。

## 有効になる条件

この変数だけでは unbuffered read を有効化しません。DS4 の Engram 層があるモデルで、まず reader が起動している必要があります。また、実装上 `eg_direct` が設定されるのは Windows の GGUF 経路で、`DS4_EG_DIRECT` が設定され、`atoi` の結果が 0 以外であり、対象ファイルに Engram tensor 以外が含まれない場合です。ファイルが memory-mapped 済みならその mapping を外してから direct 対象にします（`src/dsv41/ds4_model.cu:2497-2500,2515-2538`）。

その上で比較対象になるのは、対象ファイルの read が unbuffered 分岐へ入り、unbuffered handle の open と read が成功した行だけです。1 行分の direct span が `2 * os::kDirectAlign` 以下であることも必要です。パック形式では MXFP8 行（`mx8`）と Q6_K/IQ4_NL 行（`n2 == 0`）がこの分岐の対象になり得ます。別 scale tensor を読む形式（`n2 > 0`）や条件を満たさない read は buffered fallback に進み、この診断比較は行いません（`src/dsv41/ds4_engram_io.hpp:207-234`、要求行の形式は `src/dsv41/ds4_model.cu:5535-5548`）。

Windows 以外では `open_unbuffered()` が無効 handle を返す実装なので、現在の Strata ソースではこの比較経路に入りません（`src/dsv41/ds4_os.hpp:153-178`）。

## 実行時の詳細

read worker は unbuffered read 成功後、同じファイル・offset・長さで buffered handle を開き、`os::pread_full()` で一時バッファへ読みます。buffered open/read に失敗した場合、または `memcmp` で異なる場合に `check_bad_` を1増やし、比較を試みた行数 `check_n_` も1増やします。いずれの場合も後続の通常処理は unbuffered データを使います（`src/dsv41/ds4_engram_io.hpp:213-232`）。

`EgReader::stop()` は比較行数が1以上なら stderr に次の形式で1行出します。差異がなければ `differed from a buffered read` の数値は `0` です。unbuffered read 自体が成功しない場合や、対象の Engram read がなければ、この行は出ません（`src/dsv41/ds4_engram_io.hpp:139-150`）。

```text
ds4 Engram check (DS4_EG_CHECK): <比較行数> rows read unbuffered, <差異数> differed from a buffered read
```

`docs/DETAILS.md` にはこの診断変数の追加説明は見当たりませんでした。

## 根拠

- `src/dsv41/ds4_engram_io.hpp:207-234` — direct read の条件、環境変数判定、buffered 比較、差異計数と通常処理への継続。
- `src/dsv41/ds4_engram_io.hpp:139-150,260-261` — reader 停止時の集計ログとカウンター。
- `src/dsv41/ds4_model.cu:2497-2538` — Engram reader の起動、Windows GGUF での `DS4_EG_DIRECT` と対象ファイル選択。
- `src/dsv41/ds4_model.cu:5478-5557` — 要求行の形式ごとの read 範囲と reader への投入。
- `src/dsv41/ds4_os.hpp:153-178` — unbuffered handle と OS 条件。
