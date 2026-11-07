# `STRATA_PF_PEER_CPU`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

`--peer-device` を使う prompt の MoE 計算で、通常は CPU share の対象外になる peer GPU 併用時にも、CPU share が非 resident expert の一部を計算できるようにします。この変数だけでは CPU share を開始しません。CPU pool が設定され、別変数 `STRATA_PREFILL_CPU_SHARE` または既定条件によって CPU share が有効である必要があります。

## 値と判定

`src/prefill/prefill.cpp:303-305` は `std::getenv()` の結果を `std::atoi(e) != 0` で判定します。文字列全体の検証はしません。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字 | OFF（`atoi("")` は 0） |
| 数値変換結果が 0 | OFF（例: `0`, `0abc`, 数字で始まらない文字列） |
| 数値変換結果が非 0 | ON（例: `1`, `2`, `-1`, `1abc`, 先頭空白を含む ` 1`） |

`atoi` は先頭の空白と符号、および先頭から読める整数を使い、後続文字を検査しません。整数として表現できない範囲の入力について、実装は安全な範囲制限や fallback を設けていません。読み取り結果は `pf_peer_cpu()` 内の `static const bool` に保存されるため、最初の呼び出し後にプロセス環境を変更しても再評価されません。

## 有効になる条件

- `--peer-device` の peer prompt 経路が `Prefill::set_peer()` で設定され、実際の chunk 処理に `m.pp` があること。peer 経路は MMQ prompt path を必要とし、NVFP4 expert では拒否されます。Hadamard-folded pack は警告を出して peer prompt を使わず primary 側に戻ります（`src/prefill/prefill.cpp:2574-2589`）。
- CPU pool が取得され、`STRATA_PREFILL_CPU_SHARE` の判定で share が ON であること。未設定時の既定 share は起動経路・backend・batch・モデルの cache 状態によるため、この peer 用変数だけでは有効になりません。`STRATA_PREFILL_CPU_SHARE` は未設定なら既定条件を使い、文字列が完全一致で `auto` なら計測型 share、その他は `atof` の結果を 0..1 に clamp した比率です。したがって空文字や数値に変換できない文字列は share を OFF にし、`0` も明示的に OFF にします（`src/prefill/prefill.cpp:283-296,2968-2995`; `src/program/generate.cpp:19938-19943`）。
- 対象 chunk が `stream_all` でも `pipe_chunked` でもなく、CPU pool を chunk が確保できること。layer ごとの判定には source があり、CPU share が停止済みでなく、native expert layout があることも必要です。peer がある場合に限り `STRATA_PF_PEER_CPU` がこの条件を許可します（`src/prefill/prefill.cpp:3697-3709,4867-4868`）。
- 候補 expert は当該 layer で routed rows があり、CPU が読み取れる blob を持ち、1 expert あたりの routed token 数が CPU kernel の `MAXT` 以下であるものに限られます。peer が stream または保持して計算する expert は CPU 候補から除外されます（`src/prefill/prefill.cpp:4990-5023`）。CPU share の比率に応じて候補から CPU の担当を選ぶため、変数が ON でも chunk / layer によって CPU 担当がない場合があります（同 `:5013-5032`）。

CLI 引数によるこの環境変数の上書きはありません。関連する `STRATA_PREFILL_CPU_SHARE` が share の有効化・比率を決め、`STRATA_PREFILL_CPU_SHARE_MAX` が staged chunk の上限を決めます。peer CPU share では同ファイルの既定上限は 3072 tokens です。明示された `STRATA_PREFILL_CPU_SHARE_MAX` は少なくとも `kStreamAllMinDefault`（既定 1024）に clamp されます（`src/prefill/prefill.cpp:307-320`）。

## 実行時の詳細

peer がなければこの変数による差はありません。peer がある適格な MMQ layer では、peer が担当する expert を CPU にも primary GPU にも割り当てず、CPU が担当する rows を peer の rows の前に置きます。CPU rows の後ろを peer rows の block として保ち、peer 側の combine がその開始位置 `back_at` から読む配置です（`src/prefill/prefill.cpp:4991-4998,5034-5077`）。primary GPU と peer GPU の MoE 処理を進め、CPU は別 thread で選ばれた expert を `run_split_multi_native()` により計算します。CPU rows は後で `Dm` に転送され、peer の完了を待って combine に入ります（同 `:5353-5384,5172-5204,6098-6138`）。

この変数自体についての警告・有効化ログはありません。peer 経路の初期化失敗は通常の prefill error（例: MMQ 不在、NVFP4、peer buffer 不足）になります。CPU share 用の pinned activation / rows buffer を確保できない場合は stderr に `prefill: the CPU share is off for this run: ... (RAM is short); the GPU streams every expert` を出し、その engine の share を停止して GPU に戻します（`src/prefill/prefill.cpp:4873-4877,2579-2586,2741-2742`）。別の CPU rows / row scales buffer の割り当て失敗では `prefill: cannot allocate the CPU experts' rows` または `prefill: cannot allocate the CPU experts' row scales` を返し、chunk 処理が失敗します（同 `:5138-5164`）。

## 根拠

- 直接参照と parse/cache: `src/prefill/prefill.cpp:297-305`。他の実行時参照はなく、同ファイルのコメントに説明上の参照があります（同 `:317-318,4991-4992,5055-5056`）。
- CPU share の既定値・設定判定: `src/prefill/prefill.cpp:283-296,2968-2995`; CLI 経路での arm 条件: `src/program/generate.cpp:19938-19943`。
- chunk・expert 条件、CPU/peer rows の配置と実行: `src/prefill/prefill.cpp:3697-3709,4867-4868,4990-5077,5172-5204,5353-5384,6098-6138`。
- peer prompt の受け入れ条件と初期化結果: `src/prefill/prefill.cpp:2574-2589,2741-2755`。
- `docs/DETAILS.md:1049` は通常の CPU prefill share の一般条件を説明していますが、この peer opt-in の個別条件は記載していません。ソースコメント `src/prefill/prefill.cpp:297-302` は測定例を記録していますが、ここではソース上の記録として扱い、他環境での性能を示すものとはしていません。
