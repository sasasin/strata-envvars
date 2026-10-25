# `STRATA_DS4_RAM_TIER`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数は対象外。

## 役割

DSv4.1 の MXFP4 GGUF expert 読み込みで、VRAM に載らない expert の一部を専用 RAM slot に置く tier を選びます。RAM tier が有効な場合、初期ロードでは「熱い expert を通常コピーして固定する」経路を通さず、routing profile の使用比率が高い順に RAM tier を埋めます。expert cache も有効なら、実行中により熱くなった expert をファイルから空き RAM slot に読み込む worker を起動します。

## 値と判定

モデル実装の生成時に環境変数が設定されているかを確認し、`atoi` の結果が 0 以外なら `ram_tier=true` です。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字、数値に変換できない文字列、`0` | 無効（`atoi` が 0） |
| 整数として 0 以外 | 有効。負値も有効 |

文字列全体の検証はありません。`atoi` が数値の prefix を変換するため、たとえば `1tail` は有効、`tail1` は無効です。モデル実装生成後に環境を変更しても、そのインスタンスの判定は変わりません。

## 有効になる条件

環境変数が有効でも、RAM tier の slot が確保されるには次の条件が必要です。

- `load_experts()` が MXFP4 format を検出し、`load_experts_mx()` を使うこと。この分岐は GGUF MXFP4 expert のロード経路です。他の expert format ではこのフラグを参照するロード分岐がありません。
- CPU lane の expert がファイルから参照される `file_experts` 経路であること。`warm_bytes` はこの経路で算出され、GPU 側が載せきれない expert の容量と使用可能 RAM の小さい方を基準にします。使用可能 RAM から 8 GiB の余白を残します。
- `warm_bytes > 0` かつ VRAM に載らない候補 expert があること。
- `store_gb() > 0` ではないこと。store が有効な場合、実装は `warm_bytes` を 0 にします。
- RAM allocation が成功し、少なくとも slot を1つ確保できること。実装は確保できた slot 数から1 slotを空き用に残します。部分確保により tier の容量が小さくなる場合があります。

`warm_bytes` が 0 または候補が空なら RAM tier の初期ロード処理には入りません。slot を1つも確保できない場合は tier の expert 数が 0 になり、通常の `copy_experts()` への fallback はありません。フラグ自体が無効の場合は同じ MXFP4 経路で通常の `copy_experts()` を呼び、設定に応じて CPU lane の expert を静的に RAM コピーします。

## 実行時の詳細

ロード時に VRAM に割り当てられなかった expert を、profile における同じ layer 内の使用比率で降順に並べます。RAM tier の容量は expert blob の最大サイズ単位で slot 数に換算され、確保できた分だけ先頭の熱い expert をファイルから RAM slot に読み込みます。読み込み後、元ファイルの各 matrix 範囲には `os::advise(..., false)` が呼ばれます。verbose mode では確保数、RAM量、tier に入らなかった expert 数を `ds4: RAM tier: ...` と stderr に出します。

expert cache（`o.expert_cache`）が有効で、初期 RAM tier に少なくとも1 expert が入った場合、別 worker が起動します。cache の layer 間更新時、ファイルにあるより熱い expert を空き RAM slot に読み込み、window の境界で layer の RAM mapping を切り替えます。読み込みに失敗した slot は採用されず、RAM tier 自体は初期確保分の範囲で続きます。expert cache が無効なら worker は起動せず、初期に選ばれた expert が RAM に保持されます。

RAM tier は GPU/CPU の expert 配置数を直接変えるものではなく、通常ファイルから読む CPU-lane expert のデータ保持場所を増やすものです。ソースコメントには、64 GB RAM の V100 で page cache のみより遅かった sampled result（1.4 対 2.2–2.4 tokens/s）が記されていますが、対象モデルや測定条件の詳細がないため、一般的な性能値としては扱えません。

## 根拠

- 値の読み取りと parse: `src/dsv41/ds4_model.cu:1033-1035`。
- MXFP4 format のみ `load_experts_mx()` に分岐: `src/dsv41/ds4_model.cu:4294-4296`。
- `file_experts` の RAM 予算、8 GiB margin、store による budget 無効化: `src/dsv41/ds4_model.cu:2597-2618`。
- profile 順の候補作成、無効時の `copy_experts()`、RAM tier slot 確保と初期ロード: `src/dsv41/ds4_model.cu:4049-4125`。
- verbose ログ: `src/dsv41/ds4_model.cu:4119-4124`。
- expert cache worker の起動と file-to-RAM 移動: `src/dsv41/ds4_model.cu:4117-4119,5739-5759`。
- window 境界での RAM mapping 更新: `src/dsv41/ds4_model.cu:5976-5989`。
- V100 の測定注釈: `src/dsv41/ds4_model.cu:1016-1021`。
