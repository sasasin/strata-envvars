# `STRATA_PF_HC_REGION`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査開始時の作業ツリーは `main...origin/main` で clean。

## 役割

CUDA 系 prompt の `Prefill` buffer layout で、hyper-connection (HC) 読み取り用 scratch を個別 buffer として置かず、attention / MoE 用 buffer が共有する region に重ねて配置します。対象は `xn16`, `lo`, `lo16`, `gated` と、BF16x2 HC 時の `xn16_lo`, `lo16_lo` です。値の計算や HC kernel の選択を変える分岐ではなく、scratch の配置と必要 buffer の数え方を切り替えます。

## 値と判定

`std::getenv()` の結果を `std::atoi()` に渡し、変換結果が 0 でない場合を ON とします。文字列全体の検証はありません。

| 環境変数の状態 | 判定 |
| --- | --- |
| 未設定 | OFF |
| 空文字 | `atoi("") == 0` のため OFF |
| `0`、`00`、`-0`、先頭が数値でない文字列 | 変換結果が 0 のため OFF |
| `1`、`2`、負の非ゼロ整数 | ON |
| 数値の後ろに文字が続く値（例: `1abc`） | `atoi` が読む整数部分が非ゼロなら ON。後続部分は検査しない |

値を設定しただけで ON になるわけではありません。`pf_hc_region()` は `on && !gr_unfused()` を返すため、`STRATA_GR_UNFUSED` が先頭文字 `1` で始まる場合は OFF です。`STRATA_GR_UNFUSED` の未設定・その他の値では、この抑止条件は成立しません（`src/prefill/prefill.cpp:592-596,1562-1565`）。

## 有効になる条件

- Strata の CUDA 系 prompt `Prefill` buffer layout が使われる必要があります。Metal の `Prefill::init` は別の window 経路へ早期 return し、ここで扱う CUDA buffer carve を行いません（`src/prefill/prefill.cpp:1692-1703`）。
- `STRATA_PF_HC_REGION` の `atoi` 結果が非ゼロであること。
- `STRATA_GR_UNFUSED` が先頭文字 `1` で始まらないこと。
- この設定は MMQ の有無や fused expert layout を判定していません。`pf_hc_region()` の条件は環境値と `gr_unfused()` だけです。`bytes_needed_impl()` と `carve()` は同じ判定を使い、region のサイズ見積もりと実際の配置を揃えます（`src/prefill/prefill.cpp:1562-1565,1920-1953,1993-2000,2757-2795`）。

CLI 引数による同名設定や、別の環境変数による上書きはこの読み取り経路にはありません。関連する `STRATA_GR_UNFUSED` は機能を抑止します。

## 実行時の詳細

環境変数の判定結果 `on` は `pf_hc_region()` 内の `static const bool` に保存されます。最初に `pf_hc_region()` が呼ばれた時点で一度だけ評価され、その後プロセス内で環境値を変更しても再判定されません。`STRATA_GR_UNFUSED` も同関数内で別の static 値として初回評価時に cache されます（`src/prefill/prefill.cpp:592-596,1562-1565`）。

OFF のとき、`carve()` は HC scratch を通常の割り当て列から個別に取り、共有 region の大きさには HC set を含めません。ON のときは個別割り当てを省き、`hc_set_bytes()` で算出した HC scratch のサイズを GDN、QSA、MoE set と並べて共有 region の最大サイズに含め、region の先頭を base として HC scratch を配置します。BF16x2 HC の low-half buffer も同じ条件で region 側に置かれます（`src/prefill/prefill.cpp:1566-1571,1926-1953,1993-2000`）。

HC の読み取り、投影、SwiGLU、mix、および attention half の次 half への書き込みは既存の同じ処理を通ります。したがって、この変数自体が別の演算や kernel を選ぶことはありません（`src/prefill/prefill.cpp:4001-4043,4071-4080,7335-7365,7553-7565`）。

`carve()` でこの配置を採用したときは stderr に `strata prefill: chunk <N> tokens: STRATA_PF_HC_REGION on (the hyper-connection read's scratch is in the shared region);` と出ます。OFF または `STRATA_GR_UNFUSED` による抑止時に、この変数専用の警告はありません（`src/prefill/prefill.cpp:2065-2071`）。buffer が確保できない場合は `prefill: device buffers for a chunk of ... tokens do not fit (...)` がエラー文字列になります。通常の generate 経路は `strata generate: <error>` を stderr に出して終了コード 1 を返し、layer split 経路は `do not fit` を含む場合に終了コード 2 を返します（`src/prefill/prefill.cpp:1904-1912,2100-2108`; `src/program/generate.cpp:10630-10634,19333-19337`）。

`docs/DETAILS.md:1087` は `STRATA_PF_GROUP_SCRATCH` とこの変数を同じ行で説明し、両者を「CUDA, prompt path on MMQ」と記載しています。現行ソースでは HC region の判定に MMQ 条件はなく、`STRATA_PF_GROUP_SCRATCH` との同時設定も必要ありません。DETAILS の同じ行にある 0.3–0.5 GiB の記述は二つの設定をまとめた説明で、`STRATA_PF_HC_REGION` 単独の実測値としては扱えません。ソースコメントには HC scratch を region 外に置く量について約 63 KB/token との記載がありますが、これはコメント上の目安であり、ここでは独立した測定結果として一般化しません（`src/prefill/prefill.cpp:1557-1561`）。

## 根拠

- `src/prefill/prefill.cpp:1562-1571` — 環境値の直接読み取り、`atoi` 判定、`STRATA_GR_UNFUSED` による抑止、HC set のサイズ計算。
- `src/prefill/prefill.cpp:1920-1953,1993-2000,2065-2071` — 個別 buffer と共有 region の割り当て、サイズ見積もりへの反映、ON 時のログ。
- `src/prefill/prefill.cpp:4001-4043,4071-4080,7335-7365,7553-7565` — HC read / write が同じ scratch を既存の計算フローで使う箇所。
- `src/prefill/prefill.cpp:1692-1703,1904-1912,2100-2108` — prompt 初期化の platform 分岐と buffer 確保失敗時のエラー。
- `src/program/generate.cpp:10630-10634,19333-19337` — 初期化エラーの stderr 出力と終了コード。
- `docs/DETAILS.md:1087` — 関連設定をまとめた説明。単独の有効条件・測定値はソースで確認できた範囲に限定。
