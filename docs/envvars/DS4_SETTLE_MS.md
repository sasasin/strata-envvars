# `DS4_SETTLE_MS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1（DS4）モデルの `cache_settle()` が、処理後に VRAM expert cache の入れ替えを続ける時間予算をミリ秒単位で指定します。コードコメントはこれを chunked prompt の後の処理と説明しています。対象値は `src/dsv41/ds4_model.cu` の当該関数で一度読み取られます。別の idle 中の入れ替えには `DS4_SETTLE_IDLE_MS` が使われ、この変数の予算とは独立です。

## 値と判定

`env_f()` は環境変数が未設定なら渡された既定値を返し、設定されていれば `std::atof()` の結果を `float` にして返します。`DS4_SETTLE_MS` には `800.0f` が渡され、その値を `double` に変換して予算にします。`atof` による数値変換で、文字列全体の妥当性検査やエラー通知はありません。

| 値 | コード上の結果 |
|---|---|
| 未設定 | 既定値 800 ms |
| 空文字 | `atof("")` 相当で 0。`budget <= 0` により settle を終了 |
| 正の数値 | `float` への変換後も正なら、その値を上限として swap ループを実行。`float` で 0 に丸められるほど小さい値では実行しない |
| 0、負数、数値に変換されない文字列 | 変換結果が 0 以下なら swap ループを実行しない |
| 数値の後ろに文字が続く文字列 | `atof` が変換できる先頭部分が値になる（例: `12ms` は 12） |
| NaN | `budget <= 0` は偽だが、時間比較 `経過時間 < budget` も偽となるため swap ループに入らない |
| 正の無限大 | 時間上限には到達しない。ループは swap の処理待ち数が 0 になる場合に終了する |

境界比較は `budget <= 0` および `now_ms() - t0 < budget` です。範囲制限、clamp、CLI 引数による上書きはありません。CLI の `--no-expert-cache` は予算を上書きせず、この処理そのものを無効にします。

## 有効になる条件

- DS4 モデルのこの実装経路を使用し、`cache_settle()` が呼ばれること。
- `o.expert_cache` が有効で、swap worker（`cache_ths`）が存在すること。`--no-expert-cache` を指定した場合、または worker がない場合は関数先頭で戻り、環境変数を読みません。
- 変換後の予算が正であること。0 以下では読み取った後に戻ります。

コードは CUDA API を使う `src/dsv41/ds4_model.cu` にあります。ここで確認できるのはこの DS4 実装の条件です。別 backend の実装や driver に同名変数を渡す処理は見つかりませんでした。通常の `--expert-cache` 設定は cache の有効性・容量を決めますが、`DS4_SETTLE_MS` 自体に対応する CLI オプションはありません。

## 実行時の詳細

`cache_settle()` は run 処理末尾で `cache_tick(n)` の後に呼ばれます。関数はまず `o.expert_cache` と `cache_ths` を確認します。通過すると関数ローカル `static const double budget` を初期化し、その関数が最初に実行された時点の環境値を保持します。したがって、同じプロセスで後から環境を変更しても再読み込みされません。先頭の cache 条件を満たさない呼び出しでは static の初期化も起きません。

settle 中は各 layer について、MTP layer、spare VRAM slot のない layer、swap pending の layer を飛ばし、VRAM 外にあり heat が 2.0 以上の expert を `cpu_hits` に集めます。`cache_tick_swaps(0)` で通常の swap 選択・処理を進め、`sw_inflight == 0` なら時間切れ前でも終了します。そうでなければ 1 ms sleep して予算を再確認します。これは上限時間のループであり、個々のコピー処理自体を指定時間で中断する実装ではありません。

この関数の終了時、swap が 1 件以上完了し `o.verbose` が有効なら stderr に `ds4: expert cache: %lld swaps after the prompt (%.0f ms)` を出します。0 件ならこの行は出ません。swap の VRAM への移動失敗は `ds4 cache: layer %d expert %d: the move into VRAM failed` と stderr に記録されます。settle を予算 0 以下で飛ばしたこと自体を知らせるログはありません。RAM store の preload とそのログは別の `DS4_SETTLE_STORE` 判定に属し、この変数だけでは有効化されません。

## 根拠

- `src/dsv41/ds4_model.cu:1165`: `env_f()` の未設定時既定値と `std::atof` 変換。
- `src/dsv41/ds4_model.cu:7153-7182`: settle の目的、既定予算 800 ms、終了条件、別変数による RAM store preload。
- `src/dsv41/ds4_model.cu:9531`: run 処理末尾から `cache_settle()` を呼び出す箇所。
- `src/dsv41/ds4_model.cu:3158-3172`: expert cache が有効なときの swap worker 初期化。
- `src/dsv41/ds4_model.cu:7146-7150`: verbose swap 検査ログと VRAM 移動失敗ログ。
- `src/dsv41/ds4_model.cu:7250-7327`: 通常 swap の ready 処理、slot/table 更新、swap 数の加算。
- `src/dsv41/ds4_main.cpp:1331`: `--no-expert-cache` による cache 無効化。

`docs/DETAILS.md` と候補一覧 `docs/envvars/000_envvers.md` を照合しました。候補一覧には `DS4_SETTLE_MS` がありますが、`docs/DETAILS.md` にはこの名前の記載が見つかりませんでした。性能値は実装コメント `src/dsv41/ds4_model.cu:7157-7161` に Strix Halo での fixture 条件とともに記載されていますが、この調査では測定を再実行していません。
