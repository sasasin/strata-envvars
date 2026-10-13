# `STRATA_PREFILL_STREAM_AHEAD`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有ソース。外部ライブラリの環境変数の動作は含めない。

## 役割

CUDA の prompt prefill で、stream-all 方式に入らない chunk の routed-only expert 処理を制御する。ON の場合、現在の layer の router 出力を CPU に読み戻した後に shared expert の計算を enqueue し、その後に CPU grouping と routed expert の初期アップロードを進める。また、routed expert の重みを固定の位置数先読みではなく、まだ compute 側へ渡していない stage 済み転送が最大 `STAGE` 件になる範囲で先行して stage する。`STAGE` は 8。

## 値と判定

`std::atoi()` の結果が 0 かどうかで判定する。文字列全体の妥当性は検証しない。

| 環境変数値 | 判定 |
|---|---|
| 未設定 | ON |
| 空文字 | OFF (`atoi("") == 0`) |
| `0`、`0tail`、整数として 0 になる文字列 | OFF |
| `1`、`-1`、`2tail` など `atoi()` が非 0 を返す文字列 | ON |
| 数字として読めない文字列（例: `true`） | OFF |

判定結果は `stream_ahead_enabled()` 内の `static const bool` に一度だけ保存される。最初の判定後にプロセス環境を変更しても反映されない。CLI 引数や設定ファイルによる上書きはこの関数にはない。

## 有効になる条件

`Prefill::run_impl()` の chunk ごとの `stream_all` は、リング slot 数 `m.ring` が 8 より大きく、chunk の token 数 `T` が `stream_all_min()` 以上で、かつ expert source `m.src` がある場合に有効になる。その条件を満たす stream-all 経路では、この変数は routed-only の先読みや shared expert の延期に使われない。

変数が使われるのは `!stream_all` の経路だけで、stream-all の条件を満たさない chunk では `T`、リングサイズ、expert source の状態などにかかわらず判定結果が適用される。`stream_all_min()` は `STRATA_PREFILL_STREAM_MIN` が 0 以上ならその値、そうでなければ通常 1024 tokens（CPU share が有効な場合はその上限に応じた値）である。従って「小さい chunk 専用」とは限らず、stream-all 条件を満たさない他の chunk にも効く。

## 実行時の詳細

ON の場合、`defer_shared` が真となり、router の後、CPU へ routed IDs を読み戻す前には shared expert を計算しない。IDs の readback 後、CPU 側の expert grouping を行う前に shared expert の計算を enqueue する。コードのコメントでは、この順序が CPU grouping および routed-only 経路の初期 expert upload と重なるためと説明されている。OFF の場合は router 後すぐに shared expert を enqueue する。

routed expert の staging では resident expert は転送件数に数えず、ON の場合は `pending < 8` の間に次の expert を stage する。転送 expert の compute を enqueue すると pending 件数を減らし、空いた分を次の反復で補う。これは GPU 上の転送完了数ではなく、まだ compute 側へ渡していない stage 済み転送の数である。OFF の場合は `staged <= j + 7` の位置先読みを使う。resident expert もこの位置数には含まれるため、OFF の方式は resident expert が混ざると実際の転送先行件数が少なくなる場合がある。

これは転送・計算をどの時点で enqueue するかの制御で、環境変数に応じたログ出力はこの実装箇所にはない。性能や出力の同一性については、この変数の実装箇所や参照資料に比較測定が見当たらないため断定しない。

## 根拠

- `src/prefill/prefill.cpp:107-115`: `STAGE=8`、`atoi()` 判定、未設定時 ON、static cache。
- `src/prefill/prefill.cpp:149-153,2298-2302`: stream-all の threshold と有効条件。
- `src/prefill/prefill.cpp:2967-2970,3193-3197`: shared expert の enqueue 時期。
- `src/prefill/prefill.cpp:3688-3739,3849-3871`: routed-only staging と先読み件数の扱い。

`docs/DETAILS.md` と関連設計資料を検索したが、この環境変数自体の値の判定や A/B 比較の詳細な記述は確認できなかった。ソースコメントは `STRATA_PREFILL_STREAM_AHEAD=0` を以前の routed-only upload schedule に戻す A/B 用スイッチとして説明している（`src/prefill/prefill.cpp:109`）。
