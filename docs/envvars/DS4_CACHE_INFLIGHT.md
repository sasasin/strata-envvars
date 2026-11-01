# `DS4_CACHE_INFLIGHT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

DSV4.1 エンジンの expert cache が、VRAM と CPU 側の expert を入れ替えるときに同時進行として許す VRAM swap 数を制限します。既定値は 8 です。これは RAM tier の swap 上限ではなく、`sw_inflight` で数える VRAM swap の上限です。

## 値と判定

`src/dsv41/ds4_model.cu` のモデル実装オブジェクトのメンバー初期化時に、共通 helper `env_f()` が環境値を `std::atof()` で `float` に変換します。未設定の場合だけ既定値 `kMaxSwaps`（8）が使われます。続けて `float` から `int` へ変換し、`std::max(1, ...)` で下限 1 を適用します。

| 環境値 | `c_inflight` |
|---|---:|
| unset | 8 |
| 空文字、非数値で始まる文字列、`0` | 1（`atof()` が 0 を返す） |
| 負数 | 1（整数化後、下限を適用） |
| 正の数 | 整数化で小数部を切り捨てた値。ただし 1 未満なら 1（例: `3.9` → 3、`0.9` → 1） |
| 数値の後ろに文字がある文字列 | `atof()` が読み取る数値部分を使用（例: `3x` → 3） |

文字列全体の検証や上限 clamp はありません。したがって範囲外または有限でない値について、ソース上の安全な整数化・挙動は保証されません。

## 有効になる条件

この値を使った制限が働くのは DSV4.1 の `o.expert_cache` が有効で、expert cache worker が作られた場合です。`--no-expert-cache` はこの機能を無効にします。さらに層が VRAM に収まらない expert を持ち、cache 用の spare VRAM slot がある場合に限り、実際に swap が発生し得ます。全 expert が VRAM に収まる層には spare slot がなく、swap 対象になりません。

`DS4_CACHE_THREADS` は worker 数を `max(1, min(c_inflight, 設定値または既定値1))` に制限するため、worker 数が小さければ実効並行数もそれに制約されます。別の環境変数、CLI 引数、OS/backend 分岐が `c_inflight` の値を上書きする処理は確認できませんでした。

## 実行時の詳細

`cache_tick_swaps()` は完了済み swap を反映した後、層ごとの CPU 側 expert の利用記録を調べます。最も熱い CPU 側 expert が最も冷たい VRAM expert より `c_margin` と `c_bonus` の条件で十分熱く、spare slot があり、当該層に swap が pending でなく、`sw_inflight < c_inflight` のときにだけ VRAM swap を queue へ追加し、`sw_inflight` を増やします。完了 swap を反映するとこの数を減らします。したがって設定値は swap の候補選びや閾値を変えず、同時進行数の門として働きます。

`c_inflight` はオブジェクトのメンバー初期化時に一度読み取られる値で、同一オブジェクトの存続中に環境を変更しても再評価されません。値専用のログや警告はありません。verbose 時には prompt 後に実際の swap があれば `ds4: expert cache: N swaps after the prompt (N ms)`、idle 処理後に `ds4: expert cache: N swaps in the idle (...)` が stderr に出ますが、どちらも設定値そのものは表示しません。読み取り失敗時にこの変数専用の終了・エラー経路はありません。

## 文書との照合

`docs/DETAILS.md` の expert cache 節は `--expert-cache` の予算を説明しますが、この環境変数は説明していません。既存の `docs/envvars/DS4_CACHE_THREADS.md` は、`DS4_CACHE_INFLIGHT` の既定値 8、`atof()` による変換、下限 1、および worker 数の上限としての用途に触れており、今回確認した実装と一致します。

## 根拠

- `src/dsv41/ds4_model.cu:1155-1168` — swap 上限の既定値、`env_f()` の実装、`c_inflight` の変換。
- `src/dsv41/ds4_model.cu:3158-3173` — `o.expert_cache` 条件での worker 数 clamp と worker 作成。
- `src/dsv41/ds4_model.cu:4693-4703` — expert cache 有効時に spare VRAM slot を残す条件。
- `src/dsv41/ds4_model.cu:7162-7177,7208-7236` — prompt 後・idle 中の swap 処理と `cache_tick_swaps()` 呼び出し。
- `src/dsv41/ds4_model.cu:7250-7258,7325-7355` — 完了 swap の適用、inflight 数の減算、`sw_inflight < c_inflight` による queue 制限。
- `src/dsv41/ds4_model.hpp:25-38`; `src/dsv41/ds4_main.cpp:1331` — expert cache の既定有効状態と `--no-expert-cache`。
- `docs/DETAILS.md:378-383` — expert cache の CLI 予算に関する説明。
