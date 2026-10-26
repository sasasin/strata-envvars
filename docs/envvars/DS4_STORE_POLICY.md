# `DS4_STORE_POLICY`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek V4.1 専用エンジン `strata-dsv41` が使う RAM expert store の、退避対象スロットの選択方式を指定します。GPU に載らない routed expert を RAM に保持する store が作成される場合にだけ効きます。Strata の通常エンジン全般に適用される設定ではありません。

## 値と判定

`src/dsv41/ds4_model.cu` は環境変数が設定されているかを `getenv()` で確認し、設定時は `atoi()` の結果を `ExpertStore::Policy` にキャストします。未設定時は `--ssd-policy` から得た `o.ssd_policy` を使います。

| 環境変数 | store に渡す値 | 現行実装の選択方式 |
|---|---:|---|
| 未設定 | `--ssd-policy` の値（省略時 `0`） | `0` は LRU。`1` と `2` は LFU スコア方式 |
| `0`、空文字、数値に変換できない文字列 | `0` | LRU。設定されているので CLI 値を上書きする |
| `1` | `1` | LFU スコア方式 |
| `2` | `2` | LFU スコア方式（`1` と同じ） |
| その他の整数（負数を含む） | その整数 | `0` 以外は LFU スコア方式 |

`atoi()` は文字列全体の厳密な数値検証ではありません。先頭空白と符号の後に数値があればその数値部分を読み、後続文字は無視します（例: `1xyz` は `1`）。数値部分がない場合は `0` です。空文字も `getenv()` では「設定済み」ですが、`atoi("")` は `0` なので LRU となります。

## 有効になる条件

モデル読み込み時に `init_store()` が呼ばれますが、store は `store_gb_now()` の容量が正で、layer があり、先頭 layer の形式が MXFP4 で、`file_experts` が有効な場合に限って初期化されます。`store_gb()` は GGUF 以外なら容量を `0` にします。したがって環境変数を設定しても、これらの条件を満たさない実行では選択方式に影響しません。

容量には `--ssd-cache` と `DS4_STORE_GB` などが関係しますが、それらの値が `0` または負で store が作成されなければ、この変数も使われません。store の初期化に失敗した場合は stderr に `ds4: --ssd-cache: the store could not start` と出し、store を設定しません。

## 実行時の詳細

環境変数はモデル初期化中の `init_store()` で `Cfg` を作るときに読みます。値は store の設定に渡され、退避時に候補となるのは ready 状態で、pin されておらず、GPU から visible でもないスロットです。後続の推論リクエストごとには読み直しません。

`Policy` の定義は `kLru = 0` と `kLfu = 1` の二つです。スコア計算は値が `kLru` と等しい場合だけ最終アクセス tick を使い、それ以外は expert の heat とごく小さい tick 係数を使います。heat は expert へのアクセスごとに増え、layer ごとの240アクセスごとに全 expert の heat を `0.97` 倍します。このため環境値 `2` や未知の非ゼロ値も、現在のコードでは `1` と同じ LFU スコア経路になります。

CLI の `--ssd-policy` は `lru` を `0`、`lfu` を `1`、`lfulru` を `2` に変換します。環境変数が設定されるとこの CLI 設定を置き換えます。ソース中の `Options` コメントは値 `2` を「lfu then lru」と記していますが、現行 `ExpertStore::score()` は `2` を `1` と分けずに扱います。`docs/DETAILS.md` にこの環境変数の追加説明は見当たりません。

store 作成時には stderr に `ds4: RAM store: up to ... policy %d, ...` の形式で実際に渡された数値が出ます。ここで表示される数値は解釈後の enum 値であり、`1` と `2` の実動作差を示すものではありません。

## 根拠

- `src/dsv41/ds4_model.cu:2821-2823` — モデル初期化中に `init_store()` と `preload_store()` を呼ぶ。
- `src/dsv41/ds4_model.cu:4596-4611, 4633-4636` — store 容量の決定、GGUF 条件、store 初期化の条件。
- `src/dsv41/ds4_model.cu:4657-4664, 4710-4723` — `DS4_STORE_POLICY` の読み取り、CLI 値への fallback、初期化結果とログ。
- `src/dsv41/ds4_model.hpp:37-41` — SSD cache と policy の用途・既定値のコメント。
- `src/dsv41/ds4_main.cpp:1217-1221` — `--ssd-policy` の文字列から数値への変換。
- `src/dsv41/ds4_store.hpp:48-63, 403-411, 495-524` — policy 定義、LRU/LFU のスコアと decay、退避候補の条件。
- `docs/DEEPSEEK41.md:1-9` — `src/dsv41` が DeepSeek V4.1 用の独立エンジンであること。
