# `DS4_SETTLE_IDLE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek V4.1 エンジン `strata-dsv41` のサーバーモードで、次の要求を待つアイドル時間に expert cache の入れ替え処理を走らせるかを制御します。既定は有効です。無効にしても、プロンプト処理後に行う別の settle（`DS4_SETTLE_MS`）の設定は変わりません。

## 値と判定

`ds4_main.cpp` は `std::getenv("DS4_SETTLE_IDLE")` を一度呼び、未設定なら有効、設定済みなら `std::atoi(v) != 0` を有効条件にします。文字列全体の検証はしません。

| 値 | 判定 |
| --- | --- |
| 未設定 | 有効 |
| 空文字 | 無効（`atoi("")` は 0） |
| 数値として 0 になる文字列（例: `0`, `00`, `0abc`, `abc`） | 無効 |
| 数値として非 0 になる文字列（例: `1`, `-1`, `2abc`） | 有効 |

`atoi` による変換なので、先頭の空白と符号を含む数値接頭部を読み、後続文字列は検査しません。たとえば `  +2suffix` は有効、`false` は無効です。数値として 0 か非 0 かだけで判定し、値の範囲チェックや警告はありません。数値変換の範囲を超える入力の結果はこの実装では保証されません。

## 有効になる条件

- 対象は `STRATA_BUILD_DSV41` で生成する `strata-dsv41` のサーバー経路です。`--serve` を指定していない通常の推論・採点・画像処理経路では `serve()` に入らず、この変数を読みません。DSV41 ターゲット自体はビルド時に明示して有効化する別エンジンです（`CMakeLists.txt:906-920`）。
- モデルのロードが成功して `serve()` に入った時点で判定します。ロード失敗時は `maya-ds4: <error>` を stderr に出して終了コード 1 となり、変数の判定には到達しません（`src/dsv41/ds4_main.cpp:1395-1410`）。
- 値が有効でも、モデルの `--no-expert-cache` を指定した場合、または cache worker がない場合は `settle_idle()` が直ちに戻ります。cache worker は expert cache が有効な場合に作られます（`src/dsv41/ds4_main.cpp:1331`; `src/dsv41/ds4_model.cu:3158-3172,7213-7215`）。
- cache が動いていても、置換可能な VRAM slot がない、熱い CPU 側 expert がない、または通常の入れ替え基準を満たさない場合は swap が発生しません。条件を満たすには spare slot があり、候補 expert の heat が 2 以上で、最も冷たい VRAM expert に対し `heat > cold_heat * c_margin + c_bonus` であることなどが必要です（`src/dsv41/ds4_model.cu:7218-7227,7340-7355`）。
- `DS4_SETTLE_IDLE_MS` は別の環境変数で、アイドル処理の時間上限を指定します。未設定時は 6000 ms です。`env_f()` が `atof` で値を変換し、budget は最初に条件を通過した `settle_idle()` 呼び出しで `static` に保持されます。0 以下ならループは実行されません。これは `DS4_SETTLE_IDLE` の有効・無効判定とは別です（`src/dsv41/ds4_model.cu:1165,7213-7218`）。

## 実行時の詳細

`serve()` は `settle_idle_on` を初期化時に一度だけ計算します。同じサーバープロセスで実行中に環境を書き換えても再評価されず、要求ごとの切替にもなりません。各要求の処理が終わって次の入力行を待つ直前に worker thread を開始します。入力が届くかストリームが閉じると cancel を立てて thread を join してから入力を処理します。`QUIT` を受けた場合も同じ順序で止めます（`src/dsv41/ds4_main.cpp:716-740`）。

idle worker は最大 `DS4_SETTLE_IDLE_MS` の間、非 MTP layer の CPU 側候補を集め、通常の `cache_tick_swaps(0)` による選択・swap 処理を繰り返します。候補も進行中 swap もなくなると早く終了し、繰り返しの間には 1 ms sleep します。キャンセルは周回の先頭で確認します。入力時に cache worker の queue に入っている swap を明示的に取り消す処理はなく、join は idle worker thread の終了を待ちます（`src/dsv41/ds4_model.cu:7213-7232,7250-7258,7340-7382`）。

この変数専用の警告・エラー・終了経路はありません。通常ログはなく、`--verbose` のとき、実際に worker が cache/thread 条件を通過した呼び出しの終了時に stderr へ `ds4: expert cache: <N> swaps in the idle (<ms> ms, cancelled <0|1>)` を出します。無効時または cache 条件で早期 return した場合、このログは出ません（`src/dsv41/ds4_model.cu:7213-7232`）。

## 根拠

- 全リポジトリの完全一致検索では、値を読む実装は `src/dsv41/ds4_main.cpp:721-724` の一箇所です。同ファイル `:716-740` が起動・停止と要求待ちの位置を示します。
- CLI の cache 無効化は `src/dsv41/ds4_main.cpp:1331`、ロードから server mode への経路は `:1395-1410` です。
- idle cache の早期 return、既定時間、候補作成、verbose ログは `src/dsv41/ds4_model.cu:7213-7232`。worker 作成条件は `:3158-3172`、swap の選別は `:7250-7258,7340-7382` です。
- DSV41 が別ターゲットで、`STRATA_BUILD_DSV41` が既定 OFF であることは `CMakeLists.txt:906-920` にあります。
