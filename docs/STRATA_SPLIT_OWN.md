# `STRATA_SPLIT_OWN`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有ソース。外部ライブラリ・GPU ドライバーの環境変数動作は含めない。

## 役割

`--serve` の複数 GPU layer split で、各 stage の prompt 処理用バッファを expert cache の空き領域から借りるか、独立して確保するかを選びます。借りる既定経路では prompt 終了後に借用した expert を cache に戻します。独立バッファ経路ではこの借用を避け、prompt バッファ分だけ各 GPU の expert cache に使える領域が減ります。

この変数は generate 初期化時に通常の CUDA/HIP 系実装と SYCL 実装でそれぞれ読み取られます。値を `static` cache には入れていませんが、設定判定は layer split の初期化時に一度行われ、起動後の環境変更でその実行の設定は変わりません。

## 値と判定

文字列を数値や真偽値として parse せず、次の規則で判定します（大文字小文字を区別）。

| 環境値 | 判定・結果 |
|---|---|
| 未設定 | 既定の借用経路。 |
| 先頭文字が `0`（例: `0`, `0abc`） | 借用経路。環境変数による独立バッファ化を行わない。 |
| 完全一致で `auto` | 各 GPU の VRAM に対する予約量を見て自動判定。全 GPU で閾値内なら独立バッファ、1台でも超えれば借用。 |
| 先頭文字が `1`（例: `1`, `10`, `1abc`） | 各 GPU の VRAM 閾値判定なしで独立バッファを選ぶ。 |
| その他の設定値（空文字、`true`、`AUTO` など） | 借用経路。エラーにはせず、通常は専用ログも出さない。 |

`auto` の予約量は `160 + floor(chunk_tokens * 680 / 1024) + 96 * 4` MiB です。`chunk_tokens` は `--prefill auto` または非正の chunk 指定なら 2048、それ以外は指定 chunk です。CUDA/HIP 系では `cudaGetDeviceProperties`、SYCL では対応する device info API から CUDA0 と split 先 GPU の総 VRAM を得て、各 GPU で `reserve_mib * 100 <= 12 * total_mib` の場合にだけ独立バッファを許可します。境界ちょうど 12% は許可されます。デバイス情報の取得に失敗すると独立バッファにはせず、閾値超過理由のログも出しません。

## 有効になる条件

- `--serve` と `--layer-split` により複数 GPU の split が成立していること。環境変数の判定自体が `multi_gpu` の分岐内にあります。通常の単一 GPU 実行や、`--split-device 0` で同一 GPU を指定するケースでは適用されません。
- `--no-prefill-borrow` が指定されていないこと。この引数は既に借用を止める指定なので、環境変数の判定をスキップします。
- `--split-skip-if-fits` が指定されていないこと。この引数を使う実行では環境変数の判定をスキップし、後段で split が単一 GPU 実行に切り替わる場合も借用設定を保ちます。
- 自動配置 (`--layer-split auto`) で `auto` 判定が成立した場合、配置探索の段階では独立バッファの予約を既定で差し引かず、借用時と同じ前提で境界を探索します。別環境変数 `STRATA_SPLIT_OWN_PLACE=reserve` がある場合は予約を含めて探索します。

## 実行時の詳細

明示値で独立バッファが選ばれると `o.no_prefill_borrow` を有効にし、stderr に `strata generate: layer split: every stage keeps its own prompt buffers (~... MiB each, ...-token chunks) (STRATA_SPLIT_OWN=1)` を出します。`auto` で選ばれた場合も同じログですが、末尾の `(STRATA_SPLIT_OWN=1)` は付きません。`auto` が VRAM 条件を満たさない場合は `strata generate: layer split: the prompt paths borrow from the caches (CUDA<n> has <MiB> MiB)` と出します。明示値が独立バッファ条件に当たらない場合や device 情報取得が失敗した場合、ここでは通常ログを出しません。

独立バッファ化は `--prefill auto` の処理にも影響し、独立バッファを session 用に予約するため prefill chunk を 2048 tokens に固定します。自動 split の VRAM 配置探索では、前述の `STRATA_SPLIT_OWN_PLACE` 条件を除き、独立バッファの予約を探索上はゼロとして扱います。最終的な stage の cache 容量は独立した prompt バッファ分を考慮します。

## 文書・測定値との照合

`docs/MULTI_GPU.md` は `STRATA_SPLIT_OWN=1` を opt-in とし、各 card に独立 prompt buffers を持たせると説明しています。同資料には R9700 + RX 9070 XT の測定として、独立バッファ設定で 2K prompt 1,450 tok/s、16K 2,227 tok/s、既定 borrow 系の比較値として 2K 1,265 tok/s、16K 1,950 tok/s が記載されています。また、独立バッファでは expert の常駐集合が変わり、既定出力と異なるとしています。これらは資料記載の構成・測定値であり、他の構成での性能や出力を保証するものではありません。

## 根拠

- `src/program/generate.cpp:2348-2349,2374-2398,2400-2426`: 複数 GPU 条件、値判定、自動 VRAM 判定、ログと `no_prefill_borrow` の設定。
- `src/program/generate.cpp:2464-2466,3603-3619,3639-3643,3675-3690`: prefill auto の 2048-token fallback、借用の容量計算、自動配置探索と `STRATA_SPLIT_OWN_PLACE` の相互作用。
- `sycl/src/program/generate.cpp:2083-2084,2104-2133,2134-2169`: SYCL 側の対応実装。値判定と閾値規則は CUDA/HIP 系と同じ。
- `docs/MULTI_GPU.md:76-83`: 役割と上記測定値、出力差についての資料。
