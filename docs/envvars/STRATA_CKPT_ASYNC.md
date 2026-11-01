# `STRATA_CKPT_ASYNC`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA ビルドで、会話チェックポイントの GDN 実行状態をホストへ保存するコピーを非同期化します。通常は GDN 状態をホストのチェックポイント vector へコピーしてから保存処理を進めます。有効時はまず device 上の staging buffer へコピーし、その後、background thread が pinned host buffer を経由してチェックポイント vector へ 4 MiB ずつ転送します。呼び出し側は小さい実行状態ベクトル等の保存を進められますが、チェックポイントの GDN bytes を読む処理は必要なコピーの完了を待ちます。

この変数はチェックポイント保存経路の切り替えであり、CLI 引数や設定ファイルによる上書きはありません。通常のプロンプト処理では `prompt_cache` が有効で `L >= 1` のとき `checkpoint_at` がチェックポイントを作ります。モデルに 1 MiB 以上の GDN 状態がある場合に非同期コピーの本体が使われます。

## 値と判定

CUDA 経路では `std::getenv` の結果の先頭文字が `'1'` かを判定します。文字列全体の parse は行いません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（設定済みだが先頭文字は `\0`） |
| `1` で始まる値（`1`, `10`, `1abc` など） | 有効 |
| その他（`0`, `true`, `-1`, 空白で始まる値など） | 無効 |

大文字小文字、数値としての妥当性、値の後続文字は検査されません。判定結果は `ckpt_async_on()` 内の `static const bool` に保存されます。CUDA では最初の checkpoint save 時に評価され、その後プロセス内で環境変数を変更しても反映されません。

## 有効になる条件

- `STRATA_USE_HIP`、`STRATA_HIP_GFX906`、`STRATA_GPU_METAL` のいずれも定義されていない CUDA 経路であること。HIP、gfx906 の HIP 互換ビルド、Metal では関数が常に `false` を返します。Metal は保存処理自体も Metal engine の実装へ分岐します。
- 値判定が有効であること。
- チェックポイントの GDN vector サイズが 1 MiB 以上であること。
- device staging buffer、pinned host buffer、非同期 stream の初期化に成功し、device-to-device の staging copy が成功すること。

最後の条件を満たさない場合、非同期化せず通常の GDN copy に進みます。別変数 `STRATA_CKPT_VRAM_SLOTS` が正なら、空き容量などの条件を満たした VRAM slot が staging buffer の代わりのコピー元になり、チェックポイント復元時にも該当 slot が使われることがあります。これは `STRATA_CKPT_ASYNC` 自体の値判定を変えません。`STRATA_CKPT_GATHER` は小さい状態ベクトル群の別経路を制御します。

## 実行時の詳細

`checkpoint_save` は staging buffer を再利用するため、開始時に前回の非同期コピーを join します。非同期経路では GDN 状態を device 上へコピーした後、background thread を開始して、4 MiB 単位の device-to-host 転送と host vector への memcpy を行います。thread は各 piece の転送完了を待ってから次へ進みます。save 呼び出しは thread の完了前に戻り得ます。続いて PLE や QSA indexer の小さい状態を保存します。

`conversation_checkpoint_join` は全コピー、または指定された GDN vector へのコピーだけを待ちます。復元、スナップショットの読み書き、チェックポイントの破棄・再利用など、GDN bytes を読む／解放する側が join します。保存先が破棄されるときも `SavedConversation::live_pending` が対応するコピーを待ちます。join は転送完了までは待ちますが、background copy の失敗を呼び出し元へ返しません。失敗時は stderr のログで観測できますが、失敗後の checkpoint bytes を使わないよう呼び出し側に伝える経路はこの関数にはありません。

staging buffer 等の確保に失敗したときは同期 copy に戻り、確保失敗自体についてこの分岐から専用の警告は出しません。background copy が失敗すると、次の join 時に stderr へ `strata: STRATA_CKPT_ASYNC: a checkpoint copy failed (<CUDA error>)` を出します。join は失敗状態を呼び出し元へ返しません。同期の checkpoint save が失敗した場合は `strata serve: checkpoint save: <理由>` が stderr に出て、該当 checkpoint の作成処理は失敗します。

## 根拠

- `src/core/conversation_state.cpp:208-214` — backend ごとの無効化、`getenv` の先頭文字判定、static cache。
- `src/core/conversation_state.cpp:272-279,284-290` — join の待機・失敗ログと save 開始時の前回コピー待ち。
- `src/core/conversation_state.cpp:305-363` — 1 MiB 条件、staging 資源の確保、VRAM slot 選択、background copy と同期 fallback。
- `src/core/conversation_state.cpp:344-360` — 4 MiB ごとの D2H copy、完了待ち、vector への memcpy。
- `src/core/conversation_state.cpp:386-429,517-568,622-640,696-709` — checkpoint save/restore、snapshot save/read、個別 GDN buffer の join。
- `include/strata/core/conversation_snapshot.hpp:71-79` — API 契約と reader 側の待機。
- `include/strata/core/conversation_cache.hpp:185-189` — parked image の live GDN copy を保持する lifetime token。
- `src/program/generate.cpp:1915-1920,1923-1930` — 同期 checkpoint save の失敗ログと、失敗後の GPU 状態を判断する同期。
- `src/program/generate.cpp:10801-10805,10829-10842,10913-10932` — prompt cache の checkpoint 作成条件と保存呼び出し。
- `CMakeLists.txt:80-93,684-690` — CUDA/HIP build option と `conversation_state.cpp` の engine への組み込み。
- `docs/DETAILS.md:1504-1513,1520` — 文書上の機能説明と報告済み測定値。測定値は記載された CMP 170HX / PCIe Gen2 x4 の報告であり、本調査では再測定していません。
